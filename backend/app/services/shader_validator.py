"""Shader 验证服务：静态检查 + WebGL 编译验证"""

import re
import subprocess
import tempfile
from pathlib import Path


def validate_shader_static(source: str) -> dict:
    """
    静态验证 GLSL 代码
    
    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors = []
    warnings = []
    
    # 1. 必须包含 mainImage
    if "mainImage" not in source:
        errors.append("MISSING: mainImage function not found")
    
    # 2. 不应声明系统 uniform (Shadertoy 自动注入)
    banned_decls = [
        (r"uniform\s+float\s+iTime", "iTime"),
        (r"uniform\s+vec3\s+iResolution", "iResolution"),
        (r"uniform\s+vec2\s+iResolution", "iResolution (vec2)"),
        (r"uniform\s+vec4\s+iMouse", "iMouse"),
        (r"uniform\s+int\s+iFrame", "iFrame"),
        (r"uniform\s+float\s+u_time", "u_time (非标准)"),
        (r"uniform\s+vec2\s+u_resolution", "u_resolution (非标准)"),
        (r"uniform\s+vec3\s+u_resolution", "u_resolution (非标准)"),
    ]
    for pattern, name in banned_decls:
        if re.search(pattern, source):
            errors.append(f"BANNED: uniform '{name}' is auto-injected by Shadertoy - remove declaration")
    
    # 3. 禁止 discard
    if re.search(r"\bdiscard\b", source):
        errors.append("BANNED: discard keyword (use alpha blending instead)")
    
    # 4. 检查基本的 GLSL 语法问题
    # 检查括号匹配
    open_braces = source.count("{")
    close_braces = source.count("}")
    if open_braces != close_braces:
        errors.append(f"SYNTAX: brace mismatch ({open_braces} open, {close_braces} close)")
    
    # 检查分号
    if re.search(r"\w+\s*\n\s*{", source):  # 函数声明缺少分号
        pass  # GLSL 函数定义不需要分号，忽略
    
    # 5. 检查精度声明
    if "precision" not in source and "highp" not in source and "mediump" not in source:
        warnings.append("WARN: no precision qualifier (add 'precision highp float;')")
    
    # 6. 检查输出赋值
    if "fragColor" not in source and "out vec4" not in source:
        # Shadertoy 使用 fragColor，检查是否正确
        if "void mainImage" in source:
            if not re.search(r"fragColor\s*=", source):
                errors.append("SYNTAX: mainImage must assign to fragColor")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_shader_with_glslang(source: str) -> dict:
    """
    使用 glslangValidator 进行严格语法验证（如果可用）
    
    Returns:
        {"valid": bool, "errors": list[str]}
    """
    # 检查 glslangValidator 是否可用
    try:
        subprocess.run(["glslangValidator", "--version"], capture_output=True, timeout=5)
    except (subprocess.SubprocessError, FileNotFoundError):
        # glslangValidator 不可用，返回静态检查结果
        return validate_shader_static(source)
    
    # 将 shader 包装为完整 GLSL fragment shader
    # 注意：#version 必须是第一行，移除 shader 开头的注释/空白
    clean_source = source.strip()
    # 移除开头的注释（单行或多行）
    while clean_source.startswith('//') or clean_source.startswith('/*') or clean_source.startswith('\n'):
        if clean_source.startswith('//'):
            # 移除单行注释
            newline_idx = clean_source.find('\n')
            if newline_idx != -1:
                clean_source = clean_source[newline_idx + 1:].strip()
            else:
                clean_source = ''
        elif clean_source.startswith('/*'):
            # 移除多行注释
            end_idx = clean_source.find('*/')
            if end_idx != -1:
                clean_source = clean_source[end_idx + 2:].strip()
            else:
                break  # 未结束的多行注释，保留原样
        elif clean_source.startswith('\n'):
            clean_source = clean_source[1:].strip()
    
    wrapped_source = f"""#version 310 es
precision highp float;

// Shadertoy standard uniforms
uniform float iTime;
uniform vec3 iResolution;
uniform vec4 iMouse;

out vec4 fragColor;

{clean_source}

void main() {{
    mainImage(fragColor, gl_FragCoord.xy);
}}
"""
    
    # 写入临时文件
    with tempfile.NamedTemporaryFile(suffix=".frag", delete=False) as f:
        f.write(wrapped_source.encode())
        temp_path = f.name
    
    try:
        result = subprocess.run(
            ["glslangValidator", temp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # 清理临时文件
        Path(temp_path).unlink(missing_ok=True)
        
        # glslangValidator: 0 = success, 2+ = error
        if result.returncode == 0:
            return {"valid": True, "errors": []}
        else:
            # 错误信息在 stdout（不是 stderr）
            output = result.stdout.strip() if result.stdout else ""
            error_lines = output.split("\n") if output else []
            errors = [line for line in error_lines if "ERROR" in line or "error" in line.lower()]
            return {"valid": False, "errors": errors}
    
    except subprocess.TimeoutExpired:
        Path(temp_path).unlink(missing_ok=True)
        return {"valid": False, "errors": ["Validation timeout"]}
    except Exception as e:
        Path(temp_path).unlink(missing_ok=True)
        return {"valid": False, "errors": [f"Validation error: {str(e)}"]}


def validate_shader(source: str) -> dict:
    """
    综合 shader 验证：静态检查 + glslangValidator（如果可用）
    
    Returns:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
            "can_attempt_render": bool  # 即使有 warning 也可以尝试渲染
        }
    """
    # 先做静态检查
    static_result = validate_shader_static(source)
    
    # 如果静态检查发现致命错误，直接返回
    if not static_result["valid"]:
        return {
            "valid": False,
            "errors": static_result["errors"],
            "warnings": static_result["warnings"],
            "can_attempt_render": False,
        }
    
    # 尝试 glslangValidator
    glslang_result = validate_shader_with_glslang(source)
    
    if not glslang_result["valid"]:
        return {
            "valid": False,
            "errors": glslang_result["errors"],
            "warnings": static_result["warnings"],
            "can_attempt_render": False,
        }
    
    # 验证通过，可能有 warnings
    return {
        "valid": True,
        "errors": [],
        "warnings": static_result["warnings"],
        "can_attempt_render": True,  # 有 warning 也可以尝试渲染
    }
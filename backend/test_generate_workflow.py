"""测试 Generate 强制步骤 + Anti-raymarching Self-check"""
import pytest


def test_generate_system_has_forced_workflow():
    """验证 Generate system prompt 包含强制步骤"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("generate_system")
    
    # 必须包含强制步骤标题
    assert "强制步骤序列" in sys or "强制步骤" in sys
    
    # 必须包含 4 个步骤
    assert "Step 1" in sys
    assert "Step 2" in sys
    assert "Step 3" in sys
    assert "Step 4" in sys


def test_generate_has_anti_raymarching_check():
    """验证 Generate 包含 Anti-raymarching 自检"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("generate_system")
    
    # Anti-raymarching 自检
    assert "raymarching" in sys.lower()
    assert "禁止" in sys or "rayDirection" in sys or "ro" in sys


def test_generate_has_performance_constraints():
    """验证 Generate 包含性能约束自检"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("generate_system")
    
    # 性能约束
    assert "ALU" in sys
    assert "Texture" in sys or "texture" in sys
    assert "256" in sys


def test_generate_has_operator_catalog_reference():
    """验证 Generate 引用 Operator Catalog（从 Catalog 注入）"""
    from app.services.context_assembler import build_generate_prompt
    
    state = {}
    sys, user = build_generate_prompt(state)
    
    # Operator Catalog Token
    assert "{sdf.circle}" in sys or "sdCircle" in sys
    assert "{sdf.smooth_union}" in sys or "smooth_union" in sys
    assert "{noise.fbm}" in sys or "FBM" in sys


def test_generate_has_self_check_template():
    """验证 Generate 包含 Self-check 输出格式模板"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("generate_system")
    
    # Self-check 模板
    assert "Self-check" in sys or "自检" in sys
    assert "编译检查" in sys or "编译" in sys


def test_generate_shader_output_format():
    """验证 Generate 定义了 Shader 输出格式"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("generate_system")
    
    # Shadertoy 格式
    assert "mainImage" in sys
    assert "fragColor" in sys or "fragColor" in sys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
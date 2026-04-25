"""scripts/validate-shader.py — 检查 GLSL 代码是否符合 VFX Agent 约束"""

import re
import sys


def validate_shader(source: str) -> list[str]:
    errors = []

    # 1. 必须包含 mainImage
    if "mainImage" not in source:
        errors.append("MISSING: mainImage function not found")

    # 2. 不应声明系统 uniform
    banned_decls = [
        (r"uniform\s+float\s+u_time", "u_time"),
        (r"uniform\s+vec2\s+u_resolution", "u_resolution"),
        (r"uniform\s+vec2\s+u_mouse", "u_mouse"),
    ]
    for pattern, name in banned_decls:
        if re.search(pattern, source):
            errors.append(f"BANNED: explicit declaration of uniform {name} (injected by runtime)")

    # 3. 禁止 discard
    if re.search(r"\bdiscard\b", source):
        errors.append("BANNED: discard keyword (kills early-Z, use alpha/step instead)")

    # 4. 检测 3D raymarching 模式（2D/2.5D 系统不允许）
    raymarch_patterns = [
        (r"\b(raycast|raymarch|marchRay|castRay|rayDirection|traceRay)\b", "raymarching function name"),
        (r"\bsceneSDF\s*\(\s*vec3\b", "3D scene SDF (vec3 parameter) — use 2D SDF only"),
        (r"\bsdSphere\s*\(\s*vec3\b", "3D SDF primitive — use 2D equivalents"),
        (r"\bsdBox\s*\(\s*vec3\b", "3D SDF primitive — use 2D equivalents"),
        (r"\b(camera|camPos|rayOrigin|rayDir)\b", "3D camera/ray setup — not allowed in 2D system"),
        (r"\b(MAX_STEPS|MAX_MARCH|NUM_STEPS)\b.*\b\d{2,}\b", "raymarching step constant — likely 3D"),
    ]
    for pattern, desc in raymarch_patterns:
        if re.search(pattern, source, re.IGNORECASE):
            errors.append(f"SCOPE: detected 3D/raymarching pattern ({desc}) — this system is 2D/2.5D only")

    # 5. 检查不安全循环
    for_loops = re.findall(r"for\s*\(.+?;\s*(.+?)\s*<\s*(.+?)\s*;", source)
    for init, bound in for_loops:
        try:
            if int(bound) > 8:
                errors.append(f"LOOP: for-loop bound {bound} exceeds 8 iterations")
        except ValueError:
            errors.append(f"LOOP: dynamic loop bound '{bound}' not allowed")

    # 6. 检查不安全数学
    if re.search(r"/\s*(?!\d)(?!\s*max)", source) and "max(" not in source.split("/")[-1][:20]:
        # Simplified check — may have false positives
        pass

    # 7. 检查精度声明
    if "precision" not in source:
        errors.append("WARN: no precision qualifier (add 'precision highp float;')")

    # 8. 检查输出 clamp
    if "clamp" not in source:
        errors.append("WARN: no clamp on output — risk of out-of-gamut colors")

    return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate-shader.py <file.glsl>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        source = f.read()

    errors = validate_shader(source)
    if errors:
        print(f"❌ Found {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ Shader passes validation")
        sys.exit(0)
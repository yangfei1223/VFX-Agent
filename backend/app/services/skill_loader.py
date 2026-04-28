"""SkillLoader：加载 effect-dev skill 知识库并注入到 Agent context"""

from pathlib import Path
from typing import Optional


class SkillLoader:
    """加载 backend/app/skills/effect-dev/references 目录下的知识库文件"""

    SKILL_BASE_PATH = Path("app/skills/effect-dev")

    # 核心 reference 文件（按重要性排序）
    REFERENCE_FILES = {
        "sdf_operators": "references/sdf-operators.md",
        "shader_templates": "references/shader-templates.md",
        "aesthetics_rules": "references/aesthetics-rules.md",
        "noise_operators": "references/noise-operators.md",
        "lighting_transforms": "references/lighting-transforms.md",
        "texture_sampling": "references/texture-sampling.md",
        "gls_constraints": "references/gls-constraints.md",
    }

    # Shader skeleton 模板
    SKELETON_FILE = "assets/shader-skeleton.glsl"

    _cache: dict[str, str] = {}

    @classmethod
    def load_reference(cls, name: str) -> str:
        """加载指定的 reference 文件内容"""
        if name in cls._cache:
            return cls._cache[name]

        file_path = cls.SKILL_BASE_PATH / cls.REFERENCE_FILES[name]
        if not file_path.exists():
            raise FileNotFoundError(f"Skill reference not found: {file_path}")

        content = file_path.read_text()
        cls._cache[name] = content
        return content

    @classmethod
    def load_skeleton(cls) -> str:
        """加载 shader skeleton 模板"""
        if "skeleton" in cls._cache:
            return cls._cache["skeleton"]

        file_path = cls.SKILL_BASE_PATH / cls.SKELETON_FILE
        if not file_path.exists():
            # 返回默认 skeleton
            return cls._default_skeleton()

        content = file_path.read_text()
        cls._cache["skeleton"] = content
        return content

    @classmethod
    def load_all_references(cls) -> dict[str, str]:
        """加载所有 reference 文件"""
        return {name: cls.load_reference(name) for name in cls.REFERENCE_FILES}

    @classmethod
    def build_generate_context(cls) -> str:
        """
        构建 Generate Agent 的 Skill Context。
        
        包含核心知识库内容：
        - SDF Operators（算子定义）
        - Shader Templates（效果模板）
        - Aesthetics Rules（美学原则 + 性能预算）
        - GLSL Constraints（安全约束）
        """
        parts = [
            "## Skill 知识库（由 effect-dev Skill 自动注入）\n",
            "以下内容来自 effect-dev Skill 知识库，是生成 GLSL 着色器的核心参考：\n\n",
            "---\n\n",
            "### SDF Operators Reference\n",
            cls.load_reference("sdf_operators"),
            "\n---\n\n",
            "### Shader Templates Reference\n",
            cls.load_reference("shader_templates"),
            "\n---\n\n",
            "### Aesthetics & Performance Rules\n",
            cls.load_reference("aesthetics_rules"),
            "\n---\n\n",
            "### GLSL Safety Constraints\n",
            cls.load_reference("gls_constraints"),
        ]

        return "\n".join(parts)

    @classmethod
    def build_decompose_context(cls) -> str:
        """
        构建 Decompose Agent 的 Skill Context。
        
        包含：
        - SDF Operators（用于识别形状算子）
        - Shader Templates（用于识别效果类型）
        """
        parts = [
            "## Skill 知识库（由 effect-dev Skill 自动注入）\n",
            "以下内容帮助你识别和描述视效的算子组成：\n\n",
            "---\n\n",
            "### SDF Operators Reference\n",
            cls.load_reference("sdf_operators"),
            "\n---\n\n",
            "### Shader Templates Reference\n",
            cls.load_reference("shader_templates"),
        ]

        return "\n".join(parts)

    @classmethod
    def build_inspect_context(cls) -> str:
        """
        构建 Inspect Agent 的 Skill Context。
        
        包含：
        - Aesthetics Rules（用于评估质量）
        - GLSL Constraints（用于性能审计）
        """
        parts = [
            "## Skill 知识库（由 effect-dev Skill 自动注入）\n",
            "以下内容帮助你评估和给出修正指令：\n\n",
            "---\n\n",
            "### Aesthetics & Performance Rules\n",
            cls.load_reference("aesthetics_rules"),
            "\n---\n\n",
            "### GLSL Safety Constraints\n",
            cls.load_reference("gls_constraints"),
        ]

        return "\n".join(parts)

    @staticmethod
    def _default_skeleton() -> str:
        """默认 shader skeleton（如果文件不存在）"""
        return """// 效果名称：{effect_name}

// ---- 辅助函数区 ----
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// ---- 主着色函数 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // UV 计算（Shadertoy 标准）
    vec2 uv = fragCoord / iResolution.xy;
    vec2 aspect = vec2(iResolution.x / iResolution.y, 1.0);
    
    // 动画循环（使用 iTime）
    float t = fract(iTime / 2.0);
    
    // 着色逻辑
    vec3 color = vec3(uv.x, uv.y, t);
    
    // 输出（必须赋值 fragColor）
    fragColor = vec4(color, 1.0);
}
"""
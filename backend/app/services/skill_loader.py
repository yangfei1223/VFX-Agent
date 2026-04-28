"""SkillLoader：加载 effect-dev skill 知识库

Skill 知识库动态注入到 Generate Agent 的 user prompt，
而非硬编码到 system prompt。

只有 Generate Agent 加载 effect-dev skill。
Decompose 和 Inspect Agent 不加载此 skill。
"""

from pathlib import Path


class SkillLoader:
    """加载 backend/app/skills/effect-dev/references 目录下的知识库文件"""

    SKILL_BASE_PATH = Path("app/skills/effect-dev")

    # 核心 reference 文件
    REFERENCE_FILES = {
        "sdf_operators": "references/sdf-operators.md",
        "shader_templates": "references/shader-templates.md",
        "aesthetics_rules": "references/aesthetics-rules.md",
        "noise_operators": "references/noise-operators.md",
        "lighting_transforms": "references/lighting-transforms.md",
        "texture_sampling": "references/texture-sampling.md",
        "gls_constraints": "references/gls-constraints.md",
    }

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
    def build_generate_context(cls) -> str:
        """
        构建 Generate Agent 的 Skill Context。
        
        在 run() 方法中动态注入到 user prompt，包含：
        - SDF Operators（算子定义）
        - Shader Templates（效果模板）
        - Aesthetics Rules（美学原则 + 性能预算）
        - GLSL Constraints（安全约束）
        
        注意：只给 Generate Agent 使用。
        """
        parts = [
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
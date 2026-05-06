"""SkillLoader：加载 Agent 专属 skill 知识库

Skill 知识库动态注入到 Agent 的 user prompt，
而非硬编码到 system prompt。

- Decompose Agent → visual-effect-decomposition skill
- Inspect Agent → visual-effect-critique skill
- Generate Agent → effect-dev skill
"""

from pathlib import Path


class SkillLoader:
    """加载 backend/app/skills/*/references 目录下的知识库文件"""

    # Skill 路径配置
    SKILL_PATHS = {
        "decompose": Path("app/skills/visual-effect-decomposition"),
        "inspect": Path("app/skills/visual-effect-critique"),
        "generate": Path("app/skills/effect-dev"),
    }

    # effect-dev (Generate Agent)
    GENERATE_REFERENCES = {
        "sdf_operators": "references/sdf-operators.md",
        "shader_templates": "references/shader-templates.md",
        "aesthetics_rules": "references/aesthetics-rules.md",
        "noise_operators": "references/noise-operators.md",
        "lighting_transforms": "references/lighting-transforms.md",
        "texture_sampling": "references/texture-sampling.md",
        "glsl_constraints": "references/glsl-constraints.md",
    }

    # visual-effect-critique (Inspect Agent)
    INSPECT_REFERENCES = {
        "vfx_terminology": "references/vfx-terminology.md",
        "dimension_analysis": "references/dimension-analysis.md",
        "critique_examples": "references/critique-examples.md",
    }

    # visual-effect-decomposition (Decompose Agent)
    DECOMPOSE_REFERENCES = {
        "operator_catalog": "references/operator-catalog.md",
        "natural_language_schema": "references/natural-language-schema.md",  # 替代 DSL Schema
    }

    _cache: dict[str, str] = {}

    @classmethod
    def load_reference(cls, skill: str, name: str) -> str:
        """加载指定 skill 的 reference 文件内容

        Args:
            skill: "decompose" | "inspect" | "generate"
            name: reference 文件名（不含路径）
        """
        cache_key = f"{skill}/{name}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        skill_path = cls.SKILL_PATHS.get(skill)
        if not skill_path:
            raise ValueError(f"Unknown skill: {skill}")

        # 根据 skill 选择对应的 reference 字典
        ref_map = {
            "decompose": cls.DECOMPOSE_REFERENCES,
            "inspect": cls.INSPECT_REFERENCES,
            "generate": cls.GENERATE_REFERENCES,
        }

        ref_file = ref_map[skill].get(name)
        if not ref_file:
            raise ValueError(f"Unknown reference '{name}' for skill '{skill}'")

        file_path = skill_path / ref_file
        if not file_path.exists():
            raise FileNotFoundError(f"Skill reference not found: {file_path}")

        content = file_path.read_text()
        cls._cache[cache_key] = content
        return content

    @classmethod
    def build_decompose_context(cls) -> str:
        """
        构建 Decompose Agent 的 Skill Context。

        在 run() 方法中动态注入到 user prompt，包含：
        - Operator Catalog（GLSL 算子库）
        - Natural Language Schema（自然语言描述规范）
        """
        parts = [
            "### Operator Catalog\n",
            cls.load_reference("decompose", "operator_catalog"),
            "\n---\n\n",
            "### Natural Language Schema\n",
            cls.load_reference("decompose", "natural_language_schema"),
        ]

        return "\n".join(parts)

    @classmethod
    def build_inspect_context(cls) -> str:
        """
        构建 Inspect Agent 的 Skill Context。

        在 run() 方法中动态注入到 user prompt，包含：
        - VFX Terminology（专业术语词典）
        - Dimension Analysis（8 维度详细分析）
        - Critique Examples（好坏描述示例）
        """
        parts = [
            "### VFX Terminology\n",
            cls.load_reference("inspect", "vfx_terminology"),
            "\n---\n\n",
            "### Dimension Analysis\n",
            cls.load_reference("inspect", "dimension_analysis"),
            "\n---\n\n",
            "### Critique Examples\n",
            cls.load_reference("inspect", "critique_examples"),
        ]

        return "\n".join(parts)

    @classmethod
    def build_generate_context(cls) -> str:
        """
        构建 Generate Agent 的 Skill Context。

        在 run() 方法中动态注入到 user prompt，包含：
        - SDF Operators（算子定义）
        - Shader Templates（效果模板）
        - Aesthetics Rules（美学原则 + 性能预算）
        - GLSL Constraints（安全约束）
        """
        parts = [
            "### SDF Operators Reference\n",
            cls.load_reference("generate", "sdf_operators"),
            "\n---\n\n",
            "### Shader Templates Reference\n",
            cls.load_reference("generate", "shader_templates"),
            "\n---\n\n",
            "### Aesthetics & Performance Rules\n",
            cls.load_reference("generate", "aesthetics_rules"),
            "\n---\n\n",
            "### GLSL Safety Constraints\n",
            cls.load_reference("generate", "glsl_constraints"),
        ]

        return "\n".join(parts)
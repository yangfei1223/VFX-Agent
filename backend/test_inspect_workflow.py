"""测试 Inspect 强制步骤 + 反馈量化 Self-check"""
import pytest


def test_inspect_system_has_forced_workflow():
    """验证 Inspect system prompt 包含强制步骤"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # 必须包含强制步骤标题
    assert "强制步骤序列" in sys or "强制步骤" in sys
    
    # 必须包含 5 个步骤
    assert "Step 1" in sys
    assert "Step 2" in sys
    assert "Step 3" in sys
    assert "Step 4" in sys
    assert "Step 5" in sys


def test_inspect_has_8_dimension_coverage():
    """验证 Inspect 包含 8 维度评分"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # 8 维度
    dimensions = [
        "composition",
        "geometry",
        "color",
        "animation",
        "background",
        "lighting",
        "texture",
        "vfx_details"
    ]
    
    for dim in dimensions:
        assert dim in sys.lower()


def test_inspect_has_background_strictness_check():
    """验证 Inspect 包含 Background 严格性检查"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # Background strictness
    assert "strict" in sys
    assert "background" in sys.lower()
    assert "RGB" in sys


def test_inspect_prohibits_vague_feedback():
    """验证 Inspect 禁止模糊反馈"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # 禁止模糊反馈
    assert "禁止" in sys
    assert "效果不好" in sys or "模糊" in sys


def test_inspect_has_quantified_feedback_format():
    """验证 Inspect 包含量化反馈格式"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # 量化反馈示例
    assert "RGB" in sys
    assert "偏差" in sys or "error" in sys.lower()


def test_inspect_has_self_check_template():
    """验证 Inspect 包含 Self-check 输出格式模板"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("inspect_system")
    
    # Self-check 模板
    assert "Self-check" in sys or "自检" in sys
    assert "评分" in sys or "Score" in sys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""测试 Decompose 强制步骤序列"""
import pytest


def test_decompose_system_has_forced_workflow():
    """验证 Decompose system prompt 包含强制步骤"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("decompose_system")
    
    # 必须包含强制步骤标题
    assert "强制步骤序列" in sys or "强制步骤" in sys
    
    # 必须包含 4 个步骤
    assert "Step 1" in sys
    assert "Step 2" in sys
    assert "Step 3" in sys
    assert "Step 4" in sys
    
    # 必须包含 Self-check
    assert "Self-check" in sys or "自检" in sys


def test_decompose_has_closed_vocabulary():
    """验证 Decompose 包含 Closed Vocabulary（从 Catalog 注入）"""
    from app.services.context_assembler import build_decompose_prompt
    
    state = {}
    sys, user, images = build_decompose_prompt(state, "cold_start")
    
    # Closed Vocabulary Token
    assert "{effect.ripple}" in sys
    assert "{effect.glow}" in sys
    assert "{sdf.circle}" in sys


def test_decompose_has_required_fields_definition():
    """验证 Decompose 定义了强制字段"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("decompose_system")
    
    # 强制字段定义
    assert "primary_rgb" in sys
    assert "duration" in sys
    assert "edge_width" in sys
    assert "strict" in sys


def test_decompose_prohibits_vague_descriptions():
    """验证 Decompose 禁止模糊描述"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("decompose_system")
    
    # 禁止项
    assert "禁止" in sys
    assert "颜色好看" in sys or "模糊描述" in sys


def test_decompose_has_self_check_template():
    """验证 Decompose 包含 Self-check 输出格式模板"""
    from app.services.context_assembler import load_prompt
    
    sys = load_prompt("decompose_system")
    
    # Self-check 模板
    assert "评分" in sys or "Score" in sys
    assert "3 分" in sys or "3/5" in sys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
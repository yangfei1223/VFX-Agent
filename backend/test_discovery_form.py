"""测试 Discovery Form 组件结构"""
import pytest


def test_discovery_form_file_exists():
    """验证 Discovery Form 组件文件存在"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    assert form_path.exists()


def test_discovery_form_has_effect_types():
    """验证 Discovery Form 包含效果类型选项"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    content = form_path.read_text()
    
    # 必须包含 Closed Vocabulary effect types
    effect_types = ["ripple", "glow", "gradient", "frosted", "flow", "particle_dots", "sparkle"]
    
    for et in effect_types:
        assert et in content, f"Missing effect type: {et}"


def test_discovery_form_has_shape_types():
    """验证 Discovery Form 包含形状类型选项"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    content = form_path.read_text()
    
    # 必须包含 shape types
    shape_types = ["circle", "rect", "hexagon", "star"]
    
    for st in shape_types:
        assert st in content, f"Missing shape type: {st}"


def test_discovery_form_has_animation_types():
    """验证 Discovery Form 包含动画类型选项"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    content = form_path.read_text()
    
    # 必须包含 animation types
    animation_types = ["expand", "pulse", "flow", "static"]
    
    for at in animation_types:
        assert at in content, f"Missing animation type: {at}"


def test_discovery_form_has_background_constraints():
    """验证 Discovery Form 包含背景约束选项"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    content = form_path.read_text()
    
    # 必须包含 background constraints
    background_constraints = ["white_strict", "black_strict", "flexible"]
    
    for bc in background_constraints:
        assert bc in content, f"Missing background constraint: {bc}"


def test_discovery_form_onSubmit_callback():
    """验证 Discovery Form 有 onSubmit callback"""
    from pathlib import Path
    
    form_path = Path("/Users/yangfei/Code/VFX-Agent/frontend/src/components/VFXDiscoveryForm.tsx")
    content = form_path.read_text()
    
    # 必须有 onSubmit 接口
    assert "onSubmit" in content
    assert "DiscoveryAnswers" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
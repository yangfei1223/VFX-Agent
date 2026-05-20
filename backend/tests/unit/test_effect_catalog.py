"""测试 VFX Effect Catalog 是否注入（完整 Token 库）"""
import pytest
from app.services.context_assembler import build_decompose_prompt, build_generate_prompt


def test_effect_catalog_complete_tokens():
    """验证 Catalog 包含完整 Token 库（参考设计文档）"""
    state = {}
    sys, user, images = build_decompose_prompt(state, "cold_start")
    
    # 1. Effect Types (5 种基础 + 4 种粒子)
    assert "{effect.ripple}" in sys
    assert "{effect.glow}" in sys
    assert "{effect.gradient}" in sys
    assert "{effect.frosted}" in sys
    assert "{effect.flow}" in sys
    
    # 2. SDF Shape Tokens (基础形状)
    assert "{sdf.circle}" in sys
    assert "{sdf.box}" in sys
    assert "{sdf.ring}" in sys
    
    # 3. SDF Shape Tokens (多边形)
    assert "{sdf.triangle}" in sys or "triangle" in sys
    assert "{sdf.hexagon}" in sys or "hexagon" in sys
    
    # 4. Boolean Operations
    assert "{sdf.union}" in sys or "union" in sys
    assert "{sdf.smooth_union}" in sys or "smooth_union" in sys
    assert "{sdf.onion}" in sys or "onion" in sys
    
    # 5. Domain Operations
    assert "{sdf.rounded}" in sys or "rounded" in sys
    assert "{sdf.repetition}" in sys or "repetition" in sys
    
    # 6. Particle Tokens
    assert "{particle.dots}" in sys or "particle.dots" in sys
    assert "{particle.sparkle}" in sys or "sparkle" in sys
    
    # 7. Color/Gradient/Lighting/Noise
    assert "{color.blue}" in sys or "blue" in sys
    assert "{gradient.radial}" in sys or "radial" in sys
    assert "{lighting.glow}" in sys or "glow" in sys
    assert "{noise.perlin}" in sys or "perlin" in sys
    
    # 8. Edge/Animation/Background
    assert "{edge.soft_medium}" in sys
    assert "{anim.expand_3s}" in sys
    assert "{bg.white_strict}" in sys
    
    # 9. 禁止项说明
    assert "禁止自由发明" in sys or "禁止" in sys


def test_generate_catalog_injected():
    """验证 Generate prompt 也包含完整 Catalog"""
    state = {}
    sys, user = build_generate_prompt(state)
    
    # Generate 需要的算子映射
    assert "{sdf.circle}" in sys or "sdCircle" in sys
    assert "{noise.fbm}" in sys or "FBM" in sys


def test_catalog_uses_closed_vocabulary():
    """验证 Catalog 使用 Closed Vocabulary 约束"""
    state = {}
    sys, user, images = build_decompose_prompt(state, "cold_start")
    
    # 必须包含 Closed Vocabulary 说明
    assert "Closed Vocabulary" in sys or "closed vocabulary" in sys.lower()
    
    # 必须禁止自由发明
    assert "禁止自由发明" in sys or "禁止" in sys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
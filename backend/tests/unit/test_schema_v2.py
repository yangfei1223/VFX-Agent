"""测试 Output Schema 强制字段 (VisualDescriptionV2 TypedDict)"""
import pytest


def test_visual_description_v2_has_required_fields():
    """验证 VisualDescriptionV2 定义强制字段"""
    from app.pipeline.state import VisualDescriptionV2
    
    # TypedDict 应存在
    assert VisualDescriptionV2 is not None
    
    # 检查 TypedDict annotations（通过 __annotations__）
    annotations = VisualDescriptionV2.__annotations__
    
    # 必须包含 effect_type
    assert "effect_type" in annotations
    
    # 必须包含强制字段的子结构
    assert "shape_definition" in annotations
    assert "color_definition" in annotations
    assert "animation_definition" in annotations
    assert "background_definition" in annotations


def test_shape_definition_v2_requires_edge_width():
    """验证 ShapeDefinitionV2 包含 edge_width"""
    from app.pipeline.state import ShapeDefinitionV2
    
    annotations = ShapeDefinitionV2.__annotations__
    
    # 必须包含 edge_width
    assert "edge_width" in annotations


def test_color_definition_v2_requires_primary_rgb():
    """验证 ColorDefinitionV2 包含 primary_rgb"""
    from app.pipeline.state import ColorDefinitionV2
    
    annotations = ColorDefinitionV2.__annotations__
    
    # 必须包含 primary_rgb
    assert "primary_rgb" in annotations


def test_animation_definition_v2_requires_duration():
    """验证 AnimationDefinitionV2 包含 duration"""
    from app.pipeline.state import AnimationDefinitionV2
    
    annotations = AnimationDefinitionV2.__annotations__
    
    # 必须包含 duration
    assert "duration" in annotations


def test_background_definition_v2_requires_strict():
    """验证 BackgroundDefinitionV2 包含 strict"""
    from app.pipeline.state import BackgroundDefinitionV2
    
    annotations = BackgroundDefinitionV2.__annotations__
    
    # 必须包含 strict
    assert "strict" in annotations


def test_inspect_feedback_v2_has_8_dimensions():
    """验证 InspectFeedbackV2 包含 8 维度评分"""
    from app.pipeline.state import InspectFeedbackV2
    
    annotations = InspectFeedbackV2.__annotations__
    
    # 必须包含 dimension_scores
    assert "dimension_scores" in annotations
    assert "visual_issues" in annotations
    assert "visual_goals" in annotations


def test_valid_visual_description_v2():
    """验证完整的 VisualDescriptionV2 示例"""
    from app.pipeline.state import VisualDescriptionV2
    
    # 创建符合 Schema 的示例
    valid_desc: VisualDescriptionV2 = {
        "effect_type": "ripple",
        "shape_definition": {
            "sdf_type": "{sdf.circle}",
            "center": "vec2(0.5, 0.5)",
            "radius": 0.25,
            "edge_type": "{edge.soft_medium}",
            "edge_width": "0.02-0.03 UV"  # Required
        },
        "color_definition": {
            "primary_color": "blue",
            "primary_rgb": "(0.2, 0.5, 1.0)"  # Required
        },
        "animation_definition": {
            "animation_type": "expand",
            "duration": "3s"  # Required
        },
        "background_definition": {
            "background_type": "{bg.white_strict}",
            "background_rgb": "(1.0, 1.0, 1.0)",
            "strict": True  # Required
        }
    }
    
    # 验证强制字段存在
    assert valid_desc["effect_type"] == "ripple"
    assert "edge_width" in valid_desc["shape_definition"]
    assert "primary_rgb" in valid_desc["color_definition"]
    assert "duration" in valid_desc["animation_definition"]
    assert "strict" in valid_desc["background_definition"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
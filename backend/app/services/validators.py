"""VFX Token Validators - Closed Vocabulary Validation

V2.0: All visual_description tokens must come from VFX Effect Catalog.
"""

VALID_EFFECT_TYPES = {
    "{effect.ripple}",
    "{effect.glow}",
    "{effect.gradient}",
    "{effect.frosted}",
    "{effect.flow}",
}

VALID_SDF_TYPES = {
    "{sdf.circle}",
    "{sdf.box}",
    "{sdf.rounded_box}",
    "{sdf.ellipse}",
    "{sdf.segment}",
}

VALID_EDGE_TYPES = {
    "{edge.hard}",
    "{edge.soft_medium}",
    "{edge.soft_wide}",
}

VALID_BG_TYPES = {
    "{bg.white_strict}",
    "{bg.flexible}",
    "{bg.gradient}",
}

VALID_ANIM_TOKENS = {
    "{anim.expand_3s}",
    "{anim.pulse_2s}",
    "{anim.flow_4s}",
    "{anim.static}",
}


def validate_visual_description(visual_description: dict) -> list[str]:
    """Validate visual_description tokens against Closed Vocabulary.
    
    Returns list of warnings (empty if all valid).
    """
    warnings = []
    
    # effect_type
    effect_type = visual_description.get("effect_type", "")
    if effect_type and effect_type not in VALID_EFFECT_TYPES:
        # Allow legacy tokens without braces
        legacy_ok = effect_type in {"ripple", "glow", "gradient", "frosted", "flow"}
        if not legacy_ok:
            warnings.append(f"Invalid effect_type: {effect_type}")
    
    # shape_definition
    shape = visual_description.get("shape_definition", {})
    sdf_type = shape.get("sdf_type", "")
    if sdf_type and sdf_type not in VALID_SDF_TYPES:
        warnings.append(f"Invalid sdf_type: {sdf_type}")
    
    edge_type = shape.get("edge_type", "")
    if edge_type and edge_type not in VALID_EDGE_TYPES:
        warnings.append(f"Invalid edge_type: {edge_type}")
    
    # background_definition
    bg = visual_description.get("background_definition", {})
    bg_token = bg.get("bg_token", "")
    if bg_token and bg_token not in VALID_BG_TYPES:
        warnings.append(f"Invalid bg_token: {bg_token}")
    
    # animation_definition
    anim = visual_description.get("animation_definition", {})
    anim_token = anim.get("anim_token", "")
    if anim_token and anim_token not in VALID_ANIM_TOKENS:
        # Allow legacy formats like "expand_3s", "pulse_2s"
        legacy_ok = anim_token.replace("{anim.", "").replace("}", "") in {"expand_3s", "pulse_2s", "flow_4s", "static"}
        if not legacy_ok:
            warnings.append(f"Invalid anim_token: {anim_token}")
    
    return warnings


def validate_required_fields(visual_description: dict) -> list[str]:
    """Validate required fields exist per V2.0 schema.
    
    Required:
    - color_definition.primary_rgb
    - animation_definition.duration
    - shape_definition.edge_width
    - background_definition.strict
    """
    warnings = []
    
    color = visual_description.get("color_definition", {})
    if not color.get("primary_rgb"):
        warnings.append("Missing required: color_definition.primary_rgb")
    
    anim = visual_description.get("animation_definition", {})
    if not anim.get("duration"):
        warnings.append("Missing required: animation_definition.duration")
    
    shape = visual_description.get("shape_definition", {})
    if not shape.get("edge_width"):
        warnings.append("Missing required: shape_definition.edge_width")
    
    bg = visual_description.get("background_definition", {})
    if bg.get("strict") is None:
        warnings.append("Missing required: background_definition.strict")
    
    return warnings
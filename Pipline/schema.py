"""
Shared schema/constants for the Multi-Modal Evidence Review system.
Single source of truth so claim_processor.py, evaluation/evaluate.py,
and main.py never drift from problem_statement.md.
"""

OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}

ISSUE_TYPE = {
    "dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part",
    "torn_packaging", "crushed_packaging", "water_damage", "stain", "none", "unknown",
}

OBJECT_PART = {
    "car": {"front_bumper", "rear_bumper", "door", "hood", "windshield", "side_mirror",
            "headlight", "taillight", "fender", "quarter_panel", "body", "unknown"},
    "laptop": {"screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port",
               "base", "body", "unknown"},
    "package": {"box", "package_corner", "package_side", "seal", "label",
                "contents", "item", "unknown"},
}

RISK_FLAGS = {
    "none", "blurry_image", "cropped_or_obstructed", "low_light_or_glare",
    "wrong_angle", "wrong_object", "wrong_object_part", "damage_not_visible",
    "claim_mismatch", "possible_manipulation", "non_original_image",
    "text_instruction_present", "user_history_risk", "manual_review_required",
}

SEVERITY = {"none", "low", "medium", "high", "unknown"}

CLAIM_OBJECTS = {"car", "laptop", "package"}


def closest_object_part(claim_object: str, value: str) -> str:
    """Snap a model-proposed part to the allowed vocabulary for the object type."""
    allowed = OBJECT_PART.get(claim_object, {"unknown"})
    return value if value in allowed else "unknown"


def closest_issue_type(value: str) -> str:
    return value if value in ISSUE_TYPE else "unknown"


def closest_severity(value: str) -> str:
    return value if value in SEVERITY else "unknown"


def closest_claim_status(value: str) -> str:
    return value if value in CLAIM_STATUS else "not_enough_information"


def sanitize_risk_flags(flags) -> str:
    """Accepts a list or semicolon string; returns a clean, deduped, valid semicolon string."""
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split(";")]
    cleaned = []
    for f in flags:
        f = (f or "").strip()
        if f and f in RISK_FLAGS and f != "none" and f not in cleaned:
            cleaned.append(f)
    return ";".join(cleaned) if cleaned else "none"

# analyze_damage.py - UPDATED with multi-magnitude range support
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_city_wide_risk
from typing import List, Dict


def analyze_damage(pga_g: float, context: dict):
    """
    Analyze damage for a single PGA value.
    Original function — unchanged.
    """
    city = context["target_city"]
    
    # First, determine shaking intensity based on PGA thresholds
    shaking_intensity, intensity_description = _get_shaking_intensity(pga_g)
    
    # Try to get VLM analysis, fallback to PGA-based estimates if it fails
    try:
        from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
        
        vlm_result = get_damage_from_vlm(
            pga=pga_g,
            image_path="C:\\QuakeVision\\app\\static\\damage_curves.PNG"
        )
        
        # Convert VLM result to dict
        damage_5_types_dict = vlm_result.damage_estimates.dict()
        
        # Validate VLM results (cap unrealistic values based on PGA physics)
        damage_5_types_dict = _validate_vlm_results(damage_5_types_dict, pga_g)
        
        print("✓ Using VLM analysis")
        
    except Exception as e:
        print(f"⚠ Using PGA-based fallback (VLM failed: {str(e)[:100]})")
        # Generate damage estimates based on PGA thresholds
        damage_5_types_dict = _get_damage_from_pga_thresholds(pga_g)
    
    # Map to Pakistan building categories
    damage_3_types = map_to_pakistan_buildings(damage_5_types_dict)
    
    # Calculate city-wide risk using Firebase
    risk_report = calculate_city_wide_risk(
        city_name=city,
        damage_ratios=damage_3_types
    )
    
    city_pct = risk_report["city_summary"]["city_risk_percentage"]
    
    # Determine damage level based on BOTH PGA intensity and city risk
    damage_level, damage_description = _determine_damage_level(pga_g, city_pct, shaking_intensity)
    
    # Get recommended actions
    recommended_actions = _get_recommended_actions(damage_level, shaking_intensity)
    
    # Create comprehensive explanation
    explanation = (
        f"{intensity_description} ({pga_g:.4f}g PGA). "
        f"{damage_description} Estimated building damage in {city}: {city_pct:.1f}%."
    )

    return {
        "damage_level": damage_level,
        "explanation": explanation,
        "recommended_actions": recommended_actions
    }


def analyze_damage_range(pga_range: List[Dict], context: dict) -> List[Dict]:
    """
    Analyze damage for a range of PGA predictions produced by predict_pga_range().

    Args:
        pga_range:  List of dicts returned by pga_predictor.predict_pga_range().
                    Each dict must contain at minimum:
                        - magnitude  (float)
                        - pga_g      (float)
                        - pga_cms2   (float)
                        - is_input   (bool)
        context:    Same context dict used for single predictions, e.g.
                        {"target_city": "Islamabad"}
                    The same city is used for every entry in the range.

    Returns:
        List of dicts — one per magnitude — ready to pass to a graph/chart.
        Each dict contains:
            - magnitude         (float) : earthquake magnitude
            - pga_g             (float) : PGA in g
            - pga_cms2          (float) : PGA in cm/s²
            - shaking_intensity (str)   : e.g. "Strong Shaking"
            - damage_level      (str)   : e.g. "Moderate"
            - city_risk_pct     (float) : city-wide building damage %
            - explanation       (str)   : human-readable summary
            - recommended_actions (list): safety actions
            - is_input          (bool)  : True for the user's original magnitude
    """
    city = context["target_city"]
    results = []

    for entry in pga_range:
        pga_g      = entry["pga_g"]
        pga_cms2   = entry["pga_cms2"]
        magnitude  = entry["magnitude"]
        is_input   = entry.get("is_input", False)

        # ── Shaking intensity ──────────────────────────────────────────────
        shaking_intensity, intensity_description = _get_shaking_intensity(pga_g)

        # ── Building damage estimates (VLM → fallback) ─────────────────────
        try:
            from app.services.damage_analyzer.vlm_service import get_damage_from_vlm

            vlm_result = get_damage_from_vlm(
                pga=pga_g,
                image_path="C:\\QuakeVision\\app\\static\\damage_curves.PNG"
            )
            damage_5_types_dict = vlm_result.damage_estimates.dict()
            damage_5_types_dict = _validate_vlm_results(damage_5_types_dict, pga_g)
            print(f"  M{magnitude} ✓ VLM analysis")

        except Exception as e:
            print(f"  M{magnitude} ⚠ PGA-based fallback (VLM failed: {str(e)[:80]})")
            damage_5_types_dict = _get_damage_from_pga_thresholds(pga_g)

        # ── Map to Pakistan building categories ────────────────────────────
        damage_3_types = map_to_pakistan_buildings(damage_5_types_dict)

        # ── City-wide risk (Firebase) ──────────────────────────────────────
        risk_report = calculate_city_wide_risk(
            city_name=city,
            damage_ratios=damage_3_types
        )
        city_pct = risk_report["city_summary"]["city_risk_percentage"]

        # ── Final damage level ─────────────────────────────────────────────
        damage_level, damage_description = _determine_damage_level(
            pga_g, city_pct, shaking_intensity
        )

        # ── Recommended actions ────────────────────────────────────────────
        recommended_actions = _get_recommended_actions(damage_level, shaking_intensity)

        # ── Human-readable explanation ─────────────────────────────────────
        explanation = (
            f"M{magnitude}: {intensity_description} ({pga_g:.4f}g PGA). "
            f"{damage_description} "
            f"Estimated building damage in {city}: {city_pct:.1f}%."
        )

        results.append({
            "magnitude":           magnitude,
            "pga_g":               pga_g,
            "pga_cms2":            pga_cms2,
            "shaking_intensity":   shaking_intensity,
            "damage_level":        damage_level,
            "city_risk_pct":       round(city_pct, 2),
            "explanation":         explanation,
            "recommended_actions": recommended_actions,
            "is_input":            is_input,
        })

    return results


# ── Internal helpers (unchanged) ──────────────────────────────────────────────

def _get_shaking_intensity(pga_g: float):
    """Determine shaking intensity based on PGA thresholds."""
    if pga_g < 0.01:
        return "No Shaking",          "No shaking felt"
    elif pga_g < 0.05:
        return "Weak Shaking",        "Light shaking, felt by some people, minimal impact"
    elif pga_g < 0.15:
        return "Mild Shaking",        "Moderate shaking, felt by most, windows may rattle"
    elif pga_g < 0.30:
        return "Strong Shaking",      "Strong shaking, people may lose balance"
    elif pga_g < 0.50:
        return "Very Strong Shaking", "Very strong shaking, significant damage possible"
    elif pga_g < 1.0:
        return "Severe Shaking",      "Severe shaking, heavy damage likely"
    else:
        return "Extreme Shaking",     "Extreme shaking, catastrophic damage possible"


def _get_damage_from_pga_thresholds(pga_g: float):
    """Generate damage estimates based on PGA thresholds when VLM fails."""
    if pga_g < 0.01:
        return {"RCF": 0,  "RCI": 0,  "URM": 1,  "Adobe": 2,  "RubbleStone": 3}
    elif pga_g < 0.05:
        return {"RCF": 1,  "RCI": 2,  "URM": 5,  "Adobe": 8,  "RubbleStone": 10}
    elif pga_g < 0.15:
        return {"RCF": 5,  "RCI": 8,  "URM": 15, "Adobe": 25, "RubbleStone": 30}
    elif pga_g < 0.30:
        return {"RCF": 15, "RCI": 20, "URM": 40, "Adobe": 60, "RubbleStone": 70}
    elif pga_g < 0.50:
        return {"RCF": 35, "RCI": 45, "URM": 70, "Adobe": 85, "RubbleStone": 90}
    elif pga_g < 1.0:
        return {"RCF": 60, "RCI": 70, "URM": 90, "Adobe": 95, "RubbleStone": 98}
    else:
        return {"RCF": 80, "RCI": 85, "URM": 95, "Adobe": 99, "RubbleStone": 99}


def _validate_vlm_results(damage_dict: dict, pga_g: float) -> dict:
    """Validate and cap unrealistic VLM results based on PGA physics."""
    max_damage_limits = {
        bt: _get_max_damage_for_pga(pga_g, bt)
        for bt in ["RCF", "RCI", "URM", "Adobe", "RubbleStone"]
    }
    validated_dict = {}
    for building_type, damage in damage_dict.items():
        damage = int(damage) if not isinstance(damage, int) else damage
        max_limit = max_damage_limits.get(building_type, 100)
        if damage > max_limit:
            print(f"⚠ Capping {building_type}: {damage}% → {max_limit}% (PGA={pga_g:.4f}g)")
            damage = max_limit
        validated_dict[building_type] = max(0, min(100, damage))
    return validated_dict


def _get_max_damage_for_pga(pga_g: float, building_type: str) -> int:
    """Get maximum physically possible damage % for given PGA and building type."""
    vulnerability_multiplier = {
        "RCF": 1.0, "RCI": 1.2, "URM": 1.5, "Adobe": 2.0, "RubbleStone": 2.5
    }
    if pga_g < 0.01:   base_damage = 1
    elif pga_g < 0.05: base_damage = 10
    elif pga_g < 0.15: base_damage = 30
    elif pga_g < 0.30: base_damage = 60
    elif pga_g < 0.50: base_damage = 85
    elif pga_g < 1.0:  base_damage = 95
    else:              base_damage = 99
    return min(100, int(base_damage * vulnerability_multiplier.get(building_type, 1.0)))


def _determine_damage_level(pga_g: float, city_pct: float, shaking_intensity: str):
    """Determine final damage level considering PGA, city risk, and shaking intensity."""
    intensity_to_level = {
        "No Shaking":          "Negligible",
        "Weak Shaking":        "Very Low",
        "Mild Shaking":        "Low",
        "Strong Shaking":      "Moderate",
        "Very Strong Shaking": "High",
        "Severe Shaking":      "Very High",
        "Extreme Shaking":     "Critical"
    }
    base_level = intensity_to_level.get(shaking_intensity, "Low")

    if city_pct < 5:
        if base_level in ["Very High", "Critical"]:   adjusted_level = "High"
        elif base_level == "High":                     adjusted_level = "Moderate"
        else:                                          adjusted_level = base_level
    elif city_pct < 15:
        if base_level == "Critical":                   adjusted_level = "Very High"
        elif base_level == "Very High":                adjusted_level = "High"
        else:                                          adjusted_level = base_level
    elif city_pct < 30:
        adjusted_level = base_level
    elif city_pct < 50:
        if base_level in ["Negligible", "Very Low"]:  adjusted_level = "Low"
        elif base_level == "Low":                      adjusted_level = "Moderate"
        else:                                          adjusted_level = base_level
    else:
        if base_level in ["Negligible", "Very Low", "Low"]: adjusted_level = "Moderate"
        elif base_level == "Moderate":                      adjusted_level = "High"
        elif base_level == "High":                          adjusted_level = "Very High"
        else:                                               adjusted_level = base_level

    descriptions = {
        "Negligible": "No significant damage expected.",
        "Very Low":   "Very minor non-structural damage possible.",
        "Low":        "Minor structural damage possible to vulnerable buildings.",
        "Moderate":   "Moderate damage likely to weak structures.",
        "High":       "Significant damage expected to many buildings.",
        "Very High":  "Extensive damage likely, some collapses possible.",
        "Critical":   "Catastrophic damage expected, widespread collapses."
    }
    return adjusted_level, descriptions.get(adjusted_level, "Damage assessment inconclusive.")


def _get_recommended_actions(damage_level: str, shaking_intensity: str):
    """Get recommended safety actions based on damage level and shaking intensity."""
    action_sets = {
        "Negligible": ["No immediate action required", "Continue normal activities"],
        "Very Low":   ["Check for loose objects", "Monitor for aftershocks"],
        "Low":        ["Inspect vulnerable structures", "Secure heavy furniture", "Prepare emergency kit"],
        "Moderate":   ["Evacuate unsafe buildings", "Avoid damaged areas", "Follow local authorities' instructions"],
        "High":       ["Immediate evacuation of affected areas", "Activate emergency response", "Set up emergency shelters"],
        "Very High":  ["Mass evacuation orders", "Deploy search and rescue teams", "Establish field hospitals"],
        "Critical":   ["National emergency declaration", "Military deployment for disaster response", "International aid requested"]
    }
    intensity_actions = {
        "Strong Shaking":      ["Be prepared for aftershocks", "Check gas and water lines"],
        "Very Strong Shaking": ["Avoid using elevators", "Stay away from windows"],
        "Severe Shaking":      ["Drop, Cover, and Hold On if shaking occurs", "Move to open areas if outside"],
        "Extreme Shaking":     ["Immediate life safety actions", "Prepare for prolonged emergency response"]
    }
    base_actions  = action_sets.get(damage_level, ["Monitor situation", "Follow official guidance"])
    extra_actions = intensity_actions.get(shaking_intensity, [])
    return base_actions + extra_actions


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simulate what pga_predictor.predict_pga_range() returns for M5.0
    mock_pga_range = [
        {"magnitude": 4.0, "pga_g": 0.03,  "pga_cms2": 29.4,  "is_input": False},
        {"magnitude": 4.5, "pga_g": 0.06,  "pga_cms2": 58.8,  "is_input": False},
        {"magnitude": 5.0, "pga_g": 0.12,  "pga_cms2": 117.7, "is_input": True},
        {"magnitude": 5.5, "pga_g": 0.22,  "pga_cms2": 215.7, "is_input": False},
        {"magnitude": 6.0, "pga_g": 0.40,  "pga_cms2": 392.3, "is_input": False},
    ]

    print("Testing analyze_damage_range():")
    print("=" * 65)
    results = analyze_damage_range(mock_pga_range, {"target_city": "Islamabad"})
    for r in results:
        marker = " ← USER INPUT" if r["is_input"] else ""
        print(
            f"  M{r['magnitude']} | {r['pga_g']:.4f}g | "
            f"{r['shaking_intensity']:<22} | {r['damage_level']:<10} | "
            f"City risk: {r['city_risk_pct']:.1f}%{marker}"
        )
# analyze_damage.py - UPDATED with PGA thresholds
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_city_wide_risk

def analyze_damage(pga_g: float, context: dict):
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


def _get_shaking_intensity(pga_g: float):
    """Determine shaking intensity based on PGA thresholds."""
    if pga_g < 0.01:
        return "No Shaking", "No shaking felt"
    elif pga_g < 0.05:
        return "Weak Shaking", "Light shaking, felt by some people, minimal impact"
    elif pga_g < 0.15:
        return "Mild Shaking", "Moderate shaking, felt by most, windows may rattle"
    elif pga_g < 0.30:
        return "Strong Shaking", "Strong shaking, people may lose balance"
    elif pga_g < 0.50:
        return "Very Strong Shaking", "Very strong shaking, significant damage possible"
    elif pga_g < 1.0:
        return "Severe Shaking", "Severe shaking, heavy damage likely"
    else:
        return "Extreme Shaking", "Extreme shaking, catastrophic damage possible"


def _get_damage_from_pga_thresholds(pga_g: float):
    """Generate damage estimates based on PGA thresholds when VLM fails."""
    # Damage percentages based on building vulnerability and PGA
    if pga_g < 0.01:
        # No Shaking: Minimal to no damage
        return {
            "RCF": 0,    # Reinforced Concrete Frame
            "RCI": 0,    # Reinforced Concrete Infill
            "URM": 1,    # Unreinforced Masonry
            "Adobe": 2,  # Adobe buildings
            "RubbleStone": 3  # Rubble Stone buildings
        }
    elif pga_g < 0.05:
        # Weak Shaking: Minimal damage
        return {
            "RCF": 1,
            "RCI": 2,
            "URM": 5,
            "Adobe": 8,
            "RubbleStone": 10
        }
    elif pga_g < 0.15:
        # Mild Shaking: Light damage
        return {
            "RCF": 5,
            "RCI": 8,
            "URM": 15,
            "Adobe": 25,
            "RubbleStone": 30
        }
    elif pga_g < 0.30:
        # Strong Shaking: Moderate damage
        return {
            "RCF": 15,
            "RCI": 20,
            "URM": 40,
            "Adobe": 60,
            "RubbleStone": 70
        }
    elif pga_g < 0.50:
        # Very Strong Shaking: Significant damage
        return {
            "RCF": 35,
            "RCI": 45,
            "URM": 70,
            "Adobe": 85,
            "RubbleStone": 90
        }
    elif pga_g < 1.0:
        # Severe Shaking: Heavy damage
        return {
            "RCF": 60,
            "RCI": 70,
            "URM": 90,
            "Adobe": 95,
            "RubbleStone": 98
        }
    else:
        # Extreme Shaking: Catastrophic damage
        return {
            "RCF": 80,
            "RCI": 85,
            "URM": 95,
            "Adobe": 99,
            "RubbleStone": 99
        }


def _validate_vlm_results(damage_dict: dict, pga_g: float) -> dict:
    """Validate and cap unrealistic VLM results based on PGA physics."""
    # Maximum reasonable damage percentages based on PGA
    max_damage_limits = {
        "RCF": _get_max_damage_for_pga(pga_g, building_type="RCF"),
        "RCI": _get_max_damage_for_pga(pga_g, building_type="RCI"),
        "URM": _get_max_damage_for_pga(pga_g, building_type="URM"),
        "Adobe": _get_max_damage_for_pga(pga_g, building_type="Adobe"),
        "RubbleStone": _get_max_damage_for_pga(pga_g, building_type="RubbleStone")
    }
    
    validated_dict = {}
    for building_type, damage in damage_dict.items():
        damage = int(damage) if not isinstance(damage, int) else damage
        
        # Apply physics-based caps
        max_limit = max_damage_limits.get(building_type, 100)
        if damage > max_limit:
            print(f"⚠ Capping unrealistic {building_type} damage: {damage}% → {max_limit}% (PGA={pga_g:.4f}g)")
            damage = max_limit
        
        # Ensure 0-100 range
        damage = max(0, min(100, damage))
        validated_dict[building_type] = damage
    
    return validated_dict


def _get_max_damage_for_pga(pga_g: float, building_type: str) -> int:
    """Get maximum physically possible damage percentage for given PGA and building type."""
    # Building vulnerability: RCF < RCI < URM < Adobe < RubbleStone
    vulnerability_multiplier = {
        "RCF": 1.0,
        "RCI": 1.2,
        "URM": 1.5,
        "Adobe": 2.0,
        "RubbleStone": 2.5
    }
    
    # Base damage curve
    if pga_g < 0.01:
        base_damage = 1
    elif pga_g < 0.05:
        base_damage = 10
    elif pga_g < 0.15:
        base_damage = 30
    elif pga_g < 0.30:
        base_damage = 60
    elif pga_g < 0.50:
        base_damage = 85
    elif pga_g < 1.0:
        base_damage = 95
    else:
        base_damage = 99
    
    multiplier = vulnerability_multiplier.get(building_type, 1.0)
    max_damage = min(100, int(base_damage * multiplier))
    
    return max_damage


def _determine_damage_level(pga_g: float, city_pct: float, shaking_intensity: str):
    """Determine final damage level considering PGA, city risk, and shaking intensity."""
    # Base level from shaking intensity
    intensity_to_level = {
        "No Shaking": "Negligible",
        "Weak Shaking": "Very Low",
        "Mild Shaking": "Low",
        "Strong Shaking": "Moderate",
        "Very Strong Shaking": "High",
        "Severe Shaking": "Very High",
        "Extreme Shaking": "Critical"
    }
    
    base_level = intensity_to_level.get(shaking_intensity, "Low")
    
    # Adjust based on city damage percentage
    if city_pct < 5:
        if base_level in ["Very High", "Critical"]:
            adjusted_level = "High"
        elif base_level in ["High"]:
            adjusted_level = "Moderate"
        else:
            adjusted_level = base_level
    elif city_pct < 15:
        if base_level in ["Critical"]:
            adjusted_level = "Very High"
        elif base_level in ["Very High"]:
            adjusted_level = "High"
        else:
            adjusted_level = base_level
    elif city_pct < 30:
        # Keep base level
        adjusted_level = base_level
    elif city_pct < 50:
        if base_level in ["Negligible", "Very Low"]:
            adjusted_level = "Low"
        elif base_level in ["Low"]:
            adjusted_level = "Moderate"
        else:
            adjusted_level = base_level
    else:
        # High damage percentage - upgrade level
        if base_level in ["Negligible", "Very Low", "Low"]:
            adjusted_level = "Moderate"
        elif base_level in ["Moderate"]:
            adjusted_level = "High"
        elif base_level in ["High"]:
            adjusted_level = "Very High"
        else:
            adjusted_level = base_level
    
    # Create damage description
    descriptions = {
        "Negligible": "No significant damage expected.",
        "Very Low": "Very minor non-structural damage possible.",
        "Low": "Minor structural damage possible to vulnerable buildings.",
        "Moderate": "Moderate damage likely to weak structures.",
        "High": "Significant damage expected to many buildings.",
        "Very High": "Extensive damage likely, some collapses possible.",
        "Critical": "Catastrophic damage expected, widespread collapses."
    }
    
    damage_desc = descriptions.get(adjusted_level, "Damage assessment inconclusive.")
    
    return adjusted_level, damage_desc


def _get_recommended_actions(damage_level: str, shaking_intensity: str):
    """Get recommended safety actions based on damage level and shaking intensity."""
    # Action sets by damage level
    action_sets = {
        "Negligible": [
            "No immediate action required",
            "Continue normal activities"
        ],
        "Very Low": [
            "Check for loose objects",
            "Monitor for aftershocks"
        ],
        "Low": [
            "Inspect vulnerable structures",
            "Secure heavy furniture",
            "Prepare emergency kit"
        ],
        "Moderate": [
            "Evacuate unsafe buildings",
            "Avoid damaged areas",
            "Follow local authorities' instructions"
        ],
        "High": [
            "Immediate evacuation of affected areas",
            "Activate emergency response",
            "Set up emergency shelters"
        ],
        "Very High": [
            "Mass evacuation orders",
            "Deploy search and rescue teams",
            "Establish field hospitals"
        ],
        "Critical": [
            "National emergency declaration",
            "Military deployment for disaster response",
            "International aid requested"
        ]
    }
    
    # Add intensity-specific actions
    intensity_actions = {
        "Strong Shaking": ["Be prepared for aftershocks", "Check gas and water lines"],
        "Very Strong Shaking": ["Avoid using elevators", "Stay away from windows"],
        "Severe Shaking": ["Drop, Cover, and Hold On if shaking occurs", "Move to open areas if outside"],
        "Extreme Shaking": ["Immediate life safety actions", "Prepare for prolonged emergency response"]
    }
    
    base_actions = action_sets.get(damage_level, ["Monitor situation", "Follow official guidance"])
    extra_actions = intensity_actions.get(shaking_intensity, [])
    
    return base_actions + extra_actions


# Test function
if __name__ == "__main__":
    # Test cases covering all thresholds
    test_cases = [
        (0.004, "Test City"),   # No Shaking
        (0.03, "Test City"),    # Weak Shaking
        (0.08, "Test City"),    # Mild Shaking
        (0.2, "Test City"),     # Strong Shaking
        (0.4, "Test City"),     # Very Strong Shaking
        (0.8, "Test City"),     # Severe Shaking
        (1.5, "Test City")      # Extreme Shaking
    ]
    
    print("🧪 Testing PGA Threshold System:")
    print("=" * 60)
    
    for pga, city in test_cases:
        print(f"\nPGA = {pga:.4f}g:")
        result = analyze_damage(pga, {"target_city": city})
        print(f"  Damage Level: {result['damage_level']}")
        print(f"  Explanation: {result['explanation']}")
        print(f"  Actions: {', '.join(result['recommended_actions'][:2])}...")
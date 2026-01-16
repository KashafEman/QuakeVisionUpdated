def analyze_damage(pga: float, input_data, distance_km: float):
    """
    Analyze damage level based on PGA value.
    Returns: (damage_level, explanation, recommended_actions)
    """
    
    # Rule-based damage classification
    if pga < 0.1:
        damage = "No Damage"
        actions = "Continue normal operations. Monitor for aftershocks."
    elif pga < 0.3:
        damage = "Minor Damage"
        actions = "Inspect for cracks in walls and ceilings. Check utilities. Secure loose objects."
    elif pga < 0.5:
        damage = "Moderate Damage"
        actions = "Evacuate if structure feels unsafe. Professional structural inspection required. Stay away from damaged areas."
    else:
        damage = "Severe Damage"
        actions = "Immediate evacuation required. Contact emergency services. Do not enter building until cleared by professionals."
    
    explanation = (
    f"PGA of {pga}g (magnitude {input_data.magnitude}, "
    f"depth {input_data.depth}km) "
    f"indicates {damage.lower()} based on seismic thresholds."
)
    
    return damage, explanation, actions

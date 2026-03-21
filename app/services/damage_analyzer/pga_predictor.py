# pga_predictor.py - FIXED VERSION
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import joblib
import pandas as pd
import numpy as np
from typing import Tuple, List, Dict
from app.config import MODEL_PATH


# Load ML model
pipeline = joblib.load(MODEL_PATH)

# Soil amplification factors for physics model
SOIL_FACTORS = {
    "Rock": 1.0,
    "Hard Rock": 0.8,
    "Soft Rock": 1.2,
    "Stiff Soil": 1.5,
    "Soft Soil": 2.0,
    "Very Soft Soil": 2.5
}


def predict_pga(
    magnitude: float,
    depth: float,
    distance_km: float,
    soil_type: str
) -> Tuple[float, float]:
    """
    Hybrid PGA prediction: ML model with physics-based correction.
    """
    # Get ML prediction with proper error handling
    try:
        ml_pga = get_ml_prediction(magnitude, depth, distance_km, soil_type)
        ml_available = True
    except Exception as e:
        print(f"ML prediction failed: {e}")
        ml_pga = 0.0
        ml_available = False
    
    # Get physics-based prediction
    physics_pga = get_physics_prediction(magnitude, depth, distance_km, soil_type)
    
    # Determine final prediction
    if ml_available:
        # Apply intelligent blending
        final_pga = blend_predictions(ml_pga, physics_pga, magnitude, distance_km)
    else:
        # Use physics only if ML fails
        final_pga = physics_pga
        print(f"Using physics-only prediction: {final_pga:.4f}g")
    
    # Apply final sanity checks
    final_pga = apply_sanity_checks(final_pga, magnitude, distance_km, soil_type)
    
    # Convert units
    pga_cms2 = final_pga * 980.665
    
    # Store for analytics
    store_predicted_pga(final_pga)
    
    return round(final_pga, 4), round(pga_cms2, 2)


def predict_pga_range(
    magnitude: float,
    depth: float,
    distance_km: float,
    soil_type: str,
    step: float = 0.5,
    spread: float = 1.0
) -> List[Dict]:
    """
    Predict PGA for a range of magnitudes around the input magnitude.

    For a given input magnitude, this generates predictions for:
        [magnitude - spread, ..., magnitude, ..., magnitude + spread]
    at increments of `step`.

    Args:
        magnitude:    The user-input (central) earthquake magnitude.
        depth:        Depth in km (same for all predictions).
        distance_km:  Distance in km (same for all predictions).
        soil_type:    Soil type string (same for all predictions).
        step:         Increment between magnitude values (default 0.5).
        spread:       How far below/above the central magnitude to go (default 1.0).

    Returns:
        A list of dicts, each containing:
            - magnitude  (float)  : the magnitude for this prediction
            - pga_g      (float)  : PGA in g
            - pga_cms2   (float)  : PGA in cm/s²
            - damage     (str)    : damage level label
            - is_input   (bool)   : True if this entry matches the user's input magnitude
    """
    # Build the list of magnitudes to evaluate
    num_steps = round(spread / step)
    magnitudes = [
        round(magnitude + i * step, 2)
        for i in range(-num_steps, num_steps + 1)
    ]

    results = []
    for mag in magnitudes:
        # Skip physically impossible magnitudes
        if mag <= 0:
            continue

        pga_g, pga_cms2 = predict_pga(mag, depth, distance_km, soil_type)
        damage = classify_damage(pga_g)

        results.append({
            "magnitude": mag,
            "pga_g": pga_g,
            "pga_cms2": pga_cms2,
            "damage": damage,
            "is_input": (mag == round(magnitude, 2))
        })

    return results


def classify_damage(pga_g: float) -> str:
    """
    Classify damage level based on PGA (in g).

    Thresholds are based on common seismic intensity scales:
        < 0.01g  -> No damage
        < 0.05g  -> Minor damage
        < 0.15g  -> Moderate damage
        < 0.35g  -> Heavy damage
        < 0.65g  -> Very heavy damage
        >= 0.65g -> Catastrophic damage
    """
    if pga_g < 0.01:
        return "No Damage"
    elif pga_g < 0.05:
        return "Minor Damage"
    elif pga_g < 0.15:
        return "Moderate Damage"
    elif pga_g < 0.35:
        return "Heavy Damage"
    elif pga_g < 0.65:
        return "Very Heavy Damage"
    else:
        return "Catastrophic Damage"


def get_ml_prediction(magnitude: float, depth: float, distance_km: float, soil_type: str) -> float:
    """
    Get prediction from ML model with proper soil type handling.
    """
    # First, find out what soil types the model expects
    expected_soil_types = get_expected_soil_types()
    
    # Map input soil type to one the model expects
    mapped_soil_type = map_soil_type_to_model(soil_type, expected_soil_types)
    
    features_df = pd.DataFrame([{
        "mag": float(magnitude),
        "depth": float(depth),
        "distance_km": float(distance_km),
        "soil_type": mapped_soil_type
    }])
    
    return float(pipeline.predict(features_df)[0])


def get_expected_soil_types():
    """
    Extract the expected soil type categories from the ML pipeline.
    """
    try:
        # Try to get categories from the pipeline
        for name, transformer in pipeline.steps:
            if hasattr(transformer, 'categories_'):
                # This is likely a OneHotEncoder or OrdinalEncoder
                if 'soil_type' in transformer.categories_:
                    return list(transformer.categories_['soil_type'])
    except:
        pass
    
    # Default soil types if we can't extract them
    # Common categories used in seismic models
    return ["rock_site", "soil_site", "rock", "soil", "stiff", "soft"]


def map_soil_type_to_model(input_soil: str, expected_categories: list) -> str:
    """
    Map input soil type to one of the model's expected categories.
    """
    input_soil_lower = input_soil.lower().strip()
    
    # Try exact match first
    for category in expected_categories:
        if input_soil_lower == category.lower():
            return category
    
    # Try partial match
    for category in expected_categories:
        category_lower = category.lower()
        if (category_lower in input_soil_lower or 
            input_soil_lower in category_lower):
            return category
    
    # Try to infer based on keywords
    if any(word in input_soil_lower for word in ["rock", "hard", "bedrock"]):
        # Look for rock-like categories
        for category in expected_categories:
            if "rock" in category.lower():
                return category
    
    if any(word in input_soil_lower for word in ["soil", "soft", "stiff", "clay", "sand"]):
        # Look for soil-like categories
        for category in expected_categories:
            if "soil" in category.lower():
                return category
        for category in expected_categories:
            if "soft" in category.lower():
                return category
    
    # Default to first category if no match found
    print(f"⚠ Could not map soil type '{input_soil}' to model categories. Using '{expected_categories[0]}'")
    return expected_categories[0]


def get_physics_prediction(magnitude: float, depth: float, distance_km: float, soil_type: str) -> float:
    """
    Get physics-based PGA prediction using attenuation relationships.
    """
    # Hypocentral distance
    hypocentral_distance = np.sqrt(distance_km**2 + depth**2)
    
    # Get soil factor
    soil_factor = SOIL_FACTORS.get(soil_type, 1.0)
    
    # Use appropriate attenuation model
    # For Pakistan/Himalayan region, Sharma (2009) is good
    return sharma_2009_model(magnitude, hypocentral_distance, soil_factor)


def sharma_2009_model(magnitude: float, distance_km: float, soil_factor: float) -> float:
    """
    Sharma et al. (2009) attenuation relationship for Himalayan region.
    """
    # Coefficients for log10(PGA)
    c1 = -1.234
    c2 = 0.847
    c3 = -1.081
    c4 = 0.0061
    
    # Calculate log10(PGA)
    log10_pga = (c1 + 
                c2 * magnitude + 
                c3 * np.log10(distance_km + 10) - 
                c4 * distance_km +
                0.255 * (soil_factor - 1))
    
    # Convert to PGA in g
    return 10**log10_pga


def blend_predictions(ml_pga: float, physics_pga: float, magnitude: float, distance_km: float) -> float:
    """
    Intelligently blend ML and physics predictions.
    """
    # Calculate confidence weights
    ml_confidence = calculate_ml_confidence(magnitude, distance_km)
    physics_confidence = 1.0 - ml_confidence
    
    # Weighted average
    blended_pga = (ml_pga * ml_confidence + physics_pga * physics_confidence)
    
    return blended_pga


def calculate_ml_confidence(magnitude: float, distance_km: float) -> float:
    """
    Calculate confidence in ML prediction.
    """
    confidence = 0.3  # Start with low confidence since ML is giving bad results
    
    # Increase confidence for scenarios similar to training (adjust based on your data)
    if 4.0 <= magnitude <= 6.0 and 10 <= distance_km <= 100:
        confidence = 0.5
    
    # Reduce confidence for extreme values
    if distance_km > 200:
        confidence *= 0.5
    
    if magnitude > 7.0:
        confidence *= 0.3
    
    return confidence


def apply_sanity_checks(pga_g: float, magnitude: float, distance_km: float, soil_type: str) -> float:
    """
    Apply physics-based sanity checks.
    """
    # ABSOLUTE MAXIMUM: 4.0g (as requested)
    ABSOLUTE_MAX_PGA = 4.0
    
    # Apply absolute maximum limit
    if pga_g > ABSOLUTE_MAX_PGA:
        print(f"⚠ SANITY CHECK: PGA {pga_g:.4f}g exceeds absolute maximum of {ABSOLUTE_MAX_PGA}g, capping")
        pga_g = ABSOLUTE_MAX_PGA
    
    # Get expected bounds
    lower_bound, upper_bound = get_expected_bounds(magnitude, distance_km, soil_type)
    
    # Apply bounds
    if pga_g < lower_bound:
        return lower_bound
    elif pga_g > upper_bound:
        # Ensure upper bound doesn't exceed absolute maximum
        return min(upper_bound, ABSOLUTE_MAX_PGA)
    
    return pga_g


def get_expected_bounds(magnitude: float, distance_km: float, soil_type: str):
    """
    Get physically reasonable bounds for PGA.
    """
    # Base bounds by magnitude
    if magnitude < 4.0:
        base_min, base_max = 0.001, 0.05
    elif magnitude < 5.0:
        base_min, base_max = 0.005, 0.15
    elif magnitude < 6.0:
        base_min, base_max = 0.02, 0.4
    elif magnitude < 7.0:
        base_min, base_max = 0.05, 0.8
    else:
        base_min, base_max = 0.1, 1.5
    
    # Adjust for distance
    if distance_km > 50:
        decay_factor = 50 / distance_km
        base_max *= decay_factor
    
    # Adjust for soil type
    soil_multiplier = SOIL_FACTORS.get(soil_type, 1.0)
    base_min *= soil_multiplier
    base_max *= soil_multiplier
    
    # Ensure reasonable ranges
    lower_bound = max(0.001, base_min)
    upper_bound = min(2.0, base_max)
    
    return lower_bound, upper_bound


# Analytics functions
_last_pga_value = None

def store_predicted_pga(pga_value: float):
    global _last_pga_value
    _last_pga_value = pga_value

def get_predicted_pga():
    if _last_pga_value is None:
        raise ValueError("No PGA has been predicted yet")
    return _last_pga_value


# Debug function to inspect model
def inspect_model():
    """
    Debug function to see what soil types the model expects.
    """
    print("Model Inspection:")
    print("=" * 50)
    
    for name, transformer in pipeline.steps:
        print(f"Step: {name} - {type(transformer).__name__}")
        
        if hasattr(transformer, 'categories_'):
            print("  Categories:")
            for col, cats in transformer.categories_.items():
                print(f"    {col}: {list(cats)}")
        
        if hasattr(transformer, 'get_feature_names_out'):
            try:
                features = transformer.get_feature_names_out()
                print(f"  Features: {list(features)}")
            except:
                pass


if __name__ == "__main__":
    # First inspect the model
    inspect_model()

    # --- Single prediction (original behaviour) ---
    print("\nSingle Prediction:")
    print("=" * 50)
    pga_g, pga_cms2 = predict_pga(6.5, 15, 200, "Rock")
    print(f"M6.5 -> PGA: {pga_g:.4f} g ({pga_cms2:.1f} cm/s²)  Damage: {classify_damage(pga_g)}")

    # --- Range prediction (new behaviour) ---
    print("\nRange Predictions around M5.0:")
    print("=" * 50)
    results = predict_pga_range(
        magnitude=5.0,
        depth=15,
        distance_km=50,
        soil_type="Rock"
    )
    for r in results:
        marker = " <-- USER INPUT" if r["is_input"] else ""
        print(
            f"  M{r['magnitude']:.1f} | PGA: {r['pga_g']:.4f}g "
            f"({r['pga_cms2']:.1f} cm/s²) | {r['damage']}{marker}"
        )


# Model expects these EXACT capitalized strings
EXACT_MODEL_CATEGORIES = [
    "Alluvial Soil",
    "Medium Soil",
    "Rock/Stiff Soil",
    "Sandy Soil",
    "Soft Soil"
]

# Map user input to exact model categories
USER_INPUT_MAPPING = {
    # User lowercase input -> Exact model category
    "alluvial soil": "Alluvial Soil",
    "medium soil": "Medium Soil",
    "rock/stiff soil": "Rock/Stiff Soil",
    "sandy soil": "Sandy Soil",
    "soft soil": "Soft Soil",
    
    # Alternative names
    "alluvial": "Alluvial Soil",
    "medium": "Medium Soil",
    "rock": "Rock/Stiff Soil",
    "stiff": "Rock/Stiff Soil",
    "stiff soil": "Rock/Stiff Soil",
    "rock/stiff": "Rock/Stiff Soil",
    "sandy": "Sandy Soil",
    "sand": "Sandy Soil",
    "soft": "Soft Soil",
    
    # Already correct (capitalized)
    "Alluvial Soil": "Alluvial Soil",
    "Medium Soil": "Medium Soil",
    "Rock/Stiff Soil": "Rock/Stiff Soil",
    "Sandy Soil": "Sandy Soil",
    "Soft Soil": "Soft Soil",
}

def map_soil_type_to_code(soil_type_str: str) -> str:
    """
    Convert soil type string to the EXACT capitalized string the model expects.
    """
    # If it's already one of the exact model categories, return as-is
    if soil_type_str in EXACT_MODEL_CATEGORIES:
        return soil_type_str
    
    # Normalize input for matching
    soil_lower = soil_type_str.lower().strip()
    
    # Try exact match in mapping
    if soil_lower in USER_INPUT_MAPPING:
        return USER_INPUT_MAPPING[soil_lower]
    
    # Try to find a match
    for user_input, exact_category in USER_INPUT_MAPPING.items():
        if user_input in soil_lower or soil_lower in user_input:
            return exact_category
    
    # Try keyword matching
    if "alluvial" in soil_lower:
        return "Alluvial Soil"
    elif "medium" in soil_lower:
        return "Medium Soil"
    elif "rock" in soil_lower or "stiff" in soil_lower:
        return "Rock/Stiff Soil"
    elif "sandy" in soil_lower or "sand" in soil_lower:
        return "Sandy Soil"
    elif "soft" in soil_lower:
        return "Soft Soil"
    
    # If not found
    raise ValueError(
        f"Invalid soil type '{soil_type_str}'. "
        f"Valid options: {', '.join(EXACT_MODEL_CATEGORIES)}"
    )

def get_soil_type_name(soil_code: str) -> str:
    """Get human-readable name for soil type code."""
    return soil_code  # Already the exact string

def get_all_soil_types() -> dict:
    """Return all valid soil types for frontend dropdown."""
    # Show user-friendly names with numeric codes
    return {
        "alluvial soil": 0,
        "medium soil": 1,
        "rock/stiff soil": 2,
        "sandy soil": 3,
        "soft soil": 4,
    }

def is_valid_soil_type(soil_type_str: str) -> bool:
    """Check if soil type string is valid."""
    try:
        map_soil_type_to_code(soil_type_str)
        return True
    except ValueError:
        return False

def get_exact_model_categories() -> list:
    """Get the exact soil categories the model expects."""
    return EXACT_MODEL_CATEGORIES
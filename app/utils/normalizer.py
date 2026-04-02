import re
import unicodedata
from typing import Any, Dict, Union

# ==========================================
# 1. STRING & TEXT NORMALIZATION
# ==========================================

def normalize_string(text: str) -> str:
    """Standardize string for case/whitespace/unicode consistency."""
    if not text or not isinstance(text, str):
        return ""
    normalized = text.lower()
    normalized = unicodedata.normalize('NFKD', normalized).encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def normalize_material_name(material: str) -> str:
    """Maps various user inputs to standard engineering material codes."""
    if not material:
        return "UNKNOWN"
        
    normalized = normalize_string(material)
    
    mapping = {
        'rcf': 'RCF', 'reinforced concrete frame': 'RCF', 'rc frame': 'RCF',
        'rci': 'RCI', 'reinforced concrete infill': 'RCI',
        'urm': 'URM', 'unreinforced masonry': 'URM', 'brick': 'URM',
        'adobe': 'Adobe', 'mud brick': 'Adobe',
        'rubble stone': 'RubbleStone', 'rubblestone': 'RubbleStone', 'stone': 'RubbleStone'
    }
    
    for pattern, standard in mapping.items():
        if pattern in normalized:
            return standard
    return material.upper()


# ==========================================
# 2. SECTOR & MATH LOGIC
# ==========================================

def normalize_sector_name(sector: str) -> str:
    """Standardize sector codes (e.g., 'i-11' -> 'I-11')."""
    if not sector or not isinstance(sector, str):
        return "UNKNOWN"
    return sector.strip().upper()


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert dirty inputs (like '7.5 magnitude') to float."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        
        # Extract first valid number from string
        cleaned = str(value).strip()
        # Find pattern: optional minus, digits, optional single dot with digits
        match = re.search(r'-?\d+(?:\.\d+)?', cleaned)
        if match:
            return float(match.group())
        return default
        
    except (ValueError, TypeError):
        return default


# ==========================================
# 3. ENGINEERING CALCULATIONS
# ==========================================

def calculate_survival_probability(material: str, damage_percent: Union[float, str]) -> float:
    """
    Core engineering logic ported from legacy code.
    Converts damage % into a survival probability.
    """
    mat_key = normalize_material_name(material).lower()
    
    # Vulnerability factors (lower = more fragile)
    factors = {
        'rcf': 0.85, 'rci': 0.75, 'urm': 0.45,
        'adobe': 0.20, 'rubblestone': 0.25
    }
    
    damage_pct = safe_float_conversion(damage_percent, 0.0)
    damage_pct = max(0.0, min(100.0, damage_pct))
    
    base_survival = 100.0 - damage_pct
    factor = factors.get(mat_key, 0.5)
    
    calibrated = base_survival * factor
    return round(max(0.0, min(100.0, calibrated)), 2)


# ==========================================
# 4. BUDGET & TIMELINE HELPERS
# ==========================================

def normalize_budget_level(budget_level: str) -> str:
    """Normalize budget level string to standard format."""
    if not budget_level or not isinstance(budget_level, str):
        return "moderate"
        
    budget_map = {
        "low": "low", "basic": "low", "economy": "low", "cheap": "low",
        "moderate": "moderate", "medium": "moderate", "standard": "moderate", "average": "moderate",
        "high": "high", "premium": "high", "luxury": "high", "expensive": "high"
    }
    
    return budget_map.get(budget_level.lower().strip(), "moderate")


def get_timeline_description(timeline_months: Union[int, str], budget_level: str) -> str:
    """Generate timeline description based on duration and budget."""
    # Convert to int safely
    try:
        months = int(timeline_months) if isinstance(timeline_months, (int, float)) else int(safe_float_conversion(timeline_months, 12))
    except (ValueError, TypeError):
        months = 12
    
    if months <= 6:
        speed = "accelerated"
    elif months <= 18:
        speed = "standard"
    else:
        speed = "extended"
    
    normalized_budget = normalize_budget_level(budget_level)
    
    if normalized_budget == "low":
        pacing = "phased to spread costs"
    elif normalized_budget == "high":
        pacing = "parallel work streams to expedite"
    else:
        pacing = "sequential with standard pacing"
    
    return f"{speed} timeline ({months} months) with {pacing}"
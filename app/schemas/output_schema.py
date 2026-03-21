from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, List

DAMAGE_LEVELS = Literal[
    "Negligible", 
    "Light", 
    "Moderate", 
    "Severe", 
    "Very Severe"
]

class DamageOutput(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "pga": 0.1568,
            "pga_cms2": 153.77,
            "damage_level": "Moderate",
            "explanation": "The predicted PGA of 0.157g suggests moderate shaking that may cause minor structural damage. Soft soil conditions amplify seismic waves.",
            "recommended_actions": "Check for structural damage, secure loose objects, prepare for aftershocks. Evacuate if in vulnerable buildings.",
            "soil_type_used": "Soft Soil"
        }
    })
    
    pga: float = Field(..., ge=0, description="Peak Ground Acceleration in g units")
    pga_cms2: float = Field(..., ge=0, description="Peak Ground Acceleration in cm/s²")
    damage_level: str = Field(..., description="Predicted damage level category")
    explanation: str = Field(..., description="Explanation of the damage prediction")
    recommended_actions: str = Field(..., description="Recommended safety actions")
    soil_type_used: str = Field(..., description="Soil type used for prediction")


class DamageRangeItem(BaseModel):
    """Single magnitude entry inside a range prediction response."""
    magnitude: float = Field(..., description="Earthquake magnitude for this entry")
    pga_g: float = Field(..., ge=0, description="Peak Ground Acceleration in g units")
    pga_cms2: float = Field(..., ge=0, description="Peak Ground Acceleration in cm/s²")
    shaking_intensity: str = Field(..., description="Shaking intensity label")
    damage_level: str = Field(..., description="Predicted damage level category")
    city_risk_pct: float = Field(..., ge=0, le=100, description="City-wide building damage percentage")
    explanation: str = Field(..., description="Explanation of the damage prediction")
    recommended_actions: List[str] = Field(..., description="Recommended safety actions")
    is_input: bool = Field(..., description="True if this is the user's original input magnitude")


class DamageRangeOutput(BaseModel):
    """Response for /predict-damage-range — one entry per magnitude."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "soil_type_used": "Rock",
            "results": [
                {
                    "magnitude": 4.0,
                    "pga_g": 0.03,
                    "pga_cms2": 29.4,
                    "shaking_intensity": "Weak Shaking",
                    "damage_level": "Very Low",
                    "city_risk_pct": 5.2,
                    "explanation": "M4.0: Light shaking...",
                    "recommended_actions": ["Check for loose objects"],
                    "is_input": False
                },
                {
                    "magnitude": 5.0,
                    "pga_g": 0.12,
                    "pga_cms2": 117.7,
                    "shaking_intensity": "Mild Shaking",
                    "damage_level": "Low",
                    "city_risk_pct": 18.4,
                    "explanation": "M5.0: Moderate shaking...",
                    "recommended_actions": ["Inspect vulnerable structures"],
                    "is_input": True
                }
            ]
        }
    })

    soil_type_used: str = Field(..., description="Soil type used for all predictions")
    results: List[DamageRangeItem] = Field(..., description="Damage results for each magnitude in the range")
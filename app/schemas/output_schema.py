
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

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
    
    pga: float = Field(
        ..., 
        ge=0,
        description="Peak Ground Acceleration in g units"
    )
    pga_cms2: float = Field(
        ..., 
        ge=0,
        description="Peak Ground Acceleration in cm/s²"
    )
    damage_level: str = Field(
        ..., 
        description="Predicted damage level category (Negligible, Light, Moderate, Severe, Very Severe)"
    )
    explanation: str = Field(
        ..., 
        description="Explanation of the damage prediction"
    )
    recommended_actions: str = Field(
        ..., 
        description="Recommended safety actions based on damage level"
    )
    soil_type_used: str = Field(
        ..., 
        description="Soil type used for prediction (human-readable format)"
    )


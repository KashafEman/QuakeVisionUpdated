from pydantic import BaseModel, Field

class EarthquakeInput(BaseModel):
    magnitude: float = Field(
        ..., 
        gt=0, 
        le=10.0, 
        description="Earthquake magnitude on Richter scale (1–10)"
    )
    
    depth: float = Field(..., ge=0, 
        le=100, 
        description="Depth of earthquake in kilometers"
    )
    
    epicenter_city: str = Field(
        ..., 
        description="City where the earthquake originated"
    )
    
    target_city: str = Field(
        ..., 
        description="City for which damage assessment is required"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "magnitude": 6.5,
                "depth": 15.0,
                "epicenter_city": "Peshawar",
                "target_city": "Islamabad"
            }
        }

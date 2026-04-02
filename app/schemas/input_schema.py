from pydantic import BaseModel, Field
from typing import Literal, Optional

class EarthquakeInput(BaseModel):
    magnitude: float = Field(
        ..., 
        gt=0, 
        le=10.0, 
        description="Earthquake magnitude on Richter scale (1–10)"
    )
    
    depth: float = Field(..., ge=0, 
        le=1000, 
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

class HomeReportRequest(BaseModel):
    city_name: str
    sector_name: str
    magnitude: float = Field(..., ge=0, le=10)
    material: str
    #risk_map: Dict[str, float]
    building_type: Literal["single_story", "multi_story", "apartment", "townhouse"] = "single_story"
    budget_level: Literal["low", "moderate", "high"] = "moderate"
    timeline_value: int = Field(default=12, ge=1)
    timeline_unit: Literal["months", "years"] = "months"
    project_size_sqft: int = Field(default=5000, ge=100, le=1_000_000)
    floors: int = Field(default=1, ge=1, le=50)
    allow_web: bool = False


class GovReportRequest(BaseModel):
    city_name: str
    sector_name: str
    magnitude: float = Field(..., ge=0, le=10)
    retrofit_capacity: int = 100
    priority_metric: str = "Save Maximum Lives"
    retrofit_style: str = "Hybrid"
    budget_level: Literal["low", "moderate", "high"] = "moderate"
    timeline_value: int = Field(default=12, ge=1)
    timeline_unit: Literal["months", "years"] = "months"
    project_size_sqft: int = Field(default=5000, ge=100, le=1_000_000)
    floors: int = Field(default=1, ge=1, le=50)
    allow_web: bool = False


class DevReportRequest(BaseModel):
    city_name: str
    site_sector: str
    magnitude: float = Field(..., ge=0, le=10)
    project_type: str
    project_name: Optional[str] = None
    building_type: Literal["residential", "commercial", "mixed-use", "industrial"] = "commercial"
    budget_level: Literal["low", "moderate", "high"] = "moderate"
    timeline_value: int = Field(default=12, ge=1)
    timeline_unit: Literal["months", "years"] = "months"
    project_size_sqft: int = Field(default=5000, ge=100, le=1_000_000)
    floors: int = Field(default=1, ge=1, le=50)
    allow_web: bool = False


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str

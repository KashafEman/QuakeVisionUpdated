from pydantic import BaseModel, Field, field_validator

class EarthquakeInput(BaseModel):
    magnitude: float = Field(
        ..., 
        gt=0, 
        le=10.0,
        description="Earthquake magnitude on Richter scale (typically 1-10)"
    )
    depth: float = Field(
        ..., 
        ge=0, 
        le=100,
        description="Depth of earthquake in kilometers"
    )
    distance_from_fault: float = Field(
        ..., 
        ge=0, 
        le=500,
        description="Distance from fault line in kilometers"
    )
    soil_type: str = Field(
        ..., 
        description="Type of soil. Use /soil-types endpoint to get valid values"
    )
    
    @field_validator('soil_type')
    @classmethod
    def validate_soil_type(cls, v):
        """Validate that soil_type is a recognized string."""
        # Import here to avoid circular imports
        from app.utils.soil_type_mapper import map_soil_type_to_code, get_all_soil_types
        
        try:
            # This returns the exact capitalized string
            mapped_value = map_soil_type_to_code(v)
            return mapped_value  # Return the mapped value, not normalized input
        except ValueError as e:
            valid_types = list(get_all_soil_types().keys())
            raise ValueError(
                f"Invalid soil type '{v}'. Valid options are: {', '.join(valid_types)}"
            )
    
    def get_soil_type_code(self) -> str:
        """Convert soil_type string to the exact string the model expects."""
        # The soil_type field already contains the mapped value from validator
        return self.soil_type
    
    class Config:
        schema_extra = {
            "example": {
                "magnitude": 6.5,
                "depth": 15.0,
                "distance_from_fault": 25.0,
                "soil_type": "rock/stiff soil"
            }
        }
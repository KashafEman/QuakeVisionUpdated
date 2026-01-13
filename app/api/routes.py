
from fastapi import APIRouter, HTTPException
from app.schemas.input_schema import EarthquakeInput
from app.schemas.output_schema import DamageOutput
from app.services.pga_predictor import predict_pga
from app.services.damage_analyzer import analyze_damage


router = APIRouter()

@router.get("/soil-types")
def get_soil_types():
    """Get all valid soil types for frontend dropdown."""
    # Import here to avoid circular imports
    from app.utils.soil_type_mapper import get_all_soil_types
    
    soil_types = get_all_soil_types()
    return {
        "soil_types": soil_types,
        "soil_types_list": list(soil_types.keys()),
        "description": "Valid soil type options for earthquake damage prediction"
    }

@router.post("/predict-damage", response_model=DamageOutput)
def predict_damage(data: EarthquakeInput):
    """
    Predict earthquake damage based on seismic parameters.
    """
    try:
        # Import here to avoid circular imports
        from app.utils.soil_type_mapper import (
            get_all_soil_types, 
            is_valid_soil_type,
            get_soil_type_name
        )
        
        # The soil_type is already validated and mapped in the input schema
        # So we can trust it's valid
        soil_type_string = data.soil_type
        
        print(f"DEBUG ROUTE: Soil type from input: '{soil_type_string}'")
        
        # Get the human-readable soil type name
        soil_type_name = get_soil_type_name(soil_type_string)
        
        # Step 1: Predict PGA (returns pga_g, pga_cms2, soil_type_name)
        pga_g, pga_cms2, _ = predict_pga(data)

        # Step 2: Analyze Damage
        damage_level, explanation, recommended_actions = analyze_damage(pga_g, data)

        return DamageOutput(
            pga=round(pga_g, 4),
            pga_cms2=round(pga_cms2, 2),
            damage_level=damage_level,
            explanation=explanation,
            recommended_actions=recommended_actions,
            soil_type_used=soil_type_name
        )
    
    except HTTPException:
        raise
    
    except ValueError as e:
        error_msg = str(e)
        from app.utils.soil_type_mapper import get_all_soil_types
        valid_types = list(get_all_soil_types().keys())
        
        if "invalid soil type" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid soil type",
                    "valid_options": valid_types,
                    "message": error_msg
                }
            )
        
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {error_msg}"
        )
    
    except Exception as e:
        error_detail = str(e)
        
        if "unknown categories" in error_detail.lower():
            from app.utils.soil_type_mapper import get_all_soil_types
            valid_types = list(get_all_soil_types().keys())
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Soil type encoding error",
                    "message": "The model encountered an unknown soil type category",
                    "valid_options": valid_types,
                    "suggestion": "Please use one of the valid soil types from /soil-types endpoint"
                }
            )
        
        raise HTTPException(
            status_code=500,
            detail="An error occurred during prediction. Please check your input parameters and try again."
        )

@router.get("/health")
def health_check():
    """Health check endpoint to verify API is running."""
    return {
        "status": "healthy",
        "service": "Earthquake Damage Prediction API",
        "available_endpoints": [
            "/soil-types",
            "/predict-damage",
            "/health"
        ]
    }

# Add the test mapping endpoint
@router.get("/test-mapping/{soil_input}")
def test_soil_mapping(soil_input: str):
    """Test how a soil input gets mapped."""
    from app.utils.soil_type_mapper import map_soil_type_to_code, get_exact_model_categories
    
    try:
        mapped = map_soil_type_to_code(soil_input)
        exact_categories = get_exact_model_categories()
        
        return {
            "input": soil_input,
            "mapped": mapped,
            "is_exact_category": mapped in exact_categories,
            "exact_categories": exact_categories
        }
    except Exception as e:
        return {"error": str(e), "input": soil_input}
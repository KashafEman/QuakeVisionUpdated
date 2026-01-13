
import joblib
import pandas as pd
from app.config import MODEL_PATH

pipeline = joblib.load(MODEL_PATH)

def predict_pga(input_data):
    """
    Predict PGA using the trained Random Forest pipeline.
    """
    # Get the soil type (already validated and mapped)
    soil_type_string = input_data.get_soil_type_code()
    
    print(f"DEBUG PREDICT_PGA: Input soil type string: '{soil_type_string}'")
    
    # Import here to avoid circular imports
    from app.utils.soil_type_mapper import get_exact_model_categories
    
    # Verify it's one of the exact categories
    exact_categories = get_exact_model_categories()
    
    if soil_type_string not in exact_categories:
        print(f"ERROR: Soil type '{soil_type_string}' not in exact categories: {exact_categories}")
        # Try to fix it
        for category in exact_categories:
            if soil_type_string.lower() == category.lower():
                soil_type_string = category
                print(f"DEBUG: Fixed to '{soil_type_string}'")
                break
    
    print(f"DEBUG PREDICT_PGA: Final soil type: '{soil_type_string}'")
    
    # Create DataFrame
    features_df = pd.DataFrame([{
        'mag': float(input_data.magnitude),
        'depth': float(input_data.depth),
        'distance_km': float(input_data.distance_from_fault),
        'soil_type': soil_type_string
    }])
    
    print(f"DEBUG PREDICT_PGA: Features being sent: {features_df.iloc[0].to_dict()}")
    
    try:
        # Predict
        pga_g = pipeline.predict(features_df)[0]
        pga_cms2 = pga_g * 980.665
        
        # Soil type name is already the exact string
        soil_type_name = soil_type_string
        
        print(f"DEBUG PREDICT_PGA: Success! PGA: {pga_g}")
        
        return round(float(pga_g), 4), round(float(pga_cms2), 2), soil_type_name
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR PREDICT_PGA: {error_msg}")
        
        raise ValueError(f"Prediction failed. Model error: {error_msg}")
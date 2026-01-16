import joblib
import pandas as pd
from app.config import MODEL_PATH

# Load trained pipeline once (good practice)
pipeline = joblib.load(MODEL_PATH)

def predict_pga(
    magnitude: float,
    depth: float,
    distance_km: float,
    soil_type: str
):
    """
    Predict PGA using the trained Random Forest pipeline.
    Soil type is inferred by the system (not user-provided).
    """

    # Build feature dataframe exactly as model was trained
    features_df = pd.DataFrame([{
        "mag": float(magnitude),
        "depth": float(depth),
        "distance_km": float(distance_km),
        "soil_type": soil_type
    }])

    try:
        pga_g = pipeline.predict(features_df)[0]
        pga_cms2 = pga_g * 980.665

        return round(float(pga_g), 4), round(float(pga_cms2), 2)

    except Exception as e:
        raise ValueError(f"PGA prediction failed: {str(e)}")

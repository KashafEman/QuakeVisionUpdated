from fastapi import APIRouter, HTTPException
from app.schemas.input_schema import EarthquakeInput
from app.schemas.output_schema import DamageOutput
from app.services.pga_predictor import predict_pga
from app.services.damage_analyzer import analyze_damage
from app.utils.geocoding import get_city_coordinates, calculate_distance_km
from app.utils.soil_inference import infer_soil_type

router = APIRouter()

@router.post("/predict-damage", response_model=DamageOutput)
def predict_damage(data: EarthquakeInput):
    try:
        epi_lat, epi_lon = get_city_coordinates(data.epicenter_city)
        tgt_lat, tgt_lon = get_city_coordinates(data.target_city)

        distance_km = calculate_distance_km(epi_lat, epi_lon, tgt_lat, tgt_lon)

        soil_type = infer_soil_type(tgt_lat, tgt_lon, city_name=data.target_city)

        pga_g, pga_cms2 = predict_pga(
            magnitude=data.magnitude,
            depth=data.depth,
            distance_km=distance_km,
            soil_type=soil_type
        )

        damage_level, explanation, actions = analyze_damage(pga_g, data, distance_km)

        return DamageOutput(
            pga=pga_g,
            pga_cms2=pga_cms2,
            damage_level=damage_level,
            explanation=explanation,
            recommended_actions=actions,
            soil_type_used=soil_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

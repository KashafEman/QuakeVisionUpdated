from fastapi import APIRouter, FastAPI, HTTPException
# from app.api import urban_planning
from app.api.state import city_risk_cache
from datetime import datetime
from app.schemas.input_schema import EarthquakeInput
from app.schemas.output_schema import DamageOutput, DamageRangeOutput, DamageRangeItem
from app.services.damage_analyzer.pga_predictor import predict_pga, predict_pga_range
from app.services.damage_analyzer.analyze_damage import analyze_damage, analyze_damage_range
from app.services.damage_analyzer.city_risk_pipeline import run_city_risk_pipeline
from app.utils.geocoding import get_city_coordinates, calculate_distance_km
from app.utils.soil_inference import infer_soil_type
from app.services.damage_analyzer.vlm_service import DamageEstimates

router = APIRouter()


@router.post("/predict-damage", response_model=DamageOutput)
def predict_damage(data: EarthquakeInput):
    """
    Original single-magnitude endpoint — unchanged.
    Returns damage result for exactly the magnitude the user provided.
    """
    try:
        # 1️⃣ Distance & soil
        epi_lat, epi_lon = get_city_coordinates(data.epicenter_city)
        tgt_lat, tgt_lon = get_city_coordinates(data.target_city)

        distance_km = calculate_distance_km(
            epi_lat, epi_lon, tgt_lat, tgt_lon
        )
        soil_type = infer_soil_type(
            tgt_lat, tgt_lon, city_name=data.target_city
        )

        # 2️⃣ PGA prediction
        pga_g, pga_cms2 = predict_pga(
            magnitude=data.magnitude,
            depth=data.depth,
            distance_km=distance_km,
            soil_type=soil_type
        )

        # 3️⃣ Full city risk pipeline (cached)
        try:
            city_risk_result = run_city_risk_pipeline(
                city_name=data.target_city,
                pga_g=pga_g
            )
            city_risk_cache[data.target_city.lower()] = {
                "input": data.dict(),
                "pga": pga_g,
                "risk_report": city_risk_result,
                "damage_estimates": city_risk_result["damage_estimates"],
                "damage_level": analyze_damage(pga_g, {"target_city": data.target_city})["damage_level"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as risk_error:
            print(f"⚠ City risk pipeline failed: {risk_error}")

        # 4️⃣ Human-readable damage
        damage_result = analyze_damage(pga_g, {"target_city": data.target_city})

        return DamageOutput(
            pga=pga_g,
            pga_cms2=pga_cms2,
            damage_level=damage_result["damage_level"],
            explanation=damage_result["explanation"],
            recommended_actions=", ".join(damage_result["recommended_actions"]),
            soil_type_used=soil_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-damage-range", response_model=DamageRangeOutput)
def predict_damage_range(data: EarthquakeInput):
    """
    Range endpoint — returns damage for 5 magnitudes around the user's input:
        [magnitude - 1.0, magnitude - 0.5, magnitude, magnitude + 0.5, magnitude + 1.0]
    All entries use the same depth, distance, soil type, and city as the user input.
    Designed for graph/chart display on the frontend.
    """
    try:
        # 1️⃣ Distance & soil (same as single endpoint)
        epi_lat, epi_lon = get_city_coordinates(data.epicenter_city)
        tgt_lat, tgt_lon = get_city_coordinates(data.target_city)

        distance_km = calculate_distance_km(
            epi_lat, epi_lon, tgt_lat, tgt_lon
        )
        soil_type = infer_soil_type(
            tgt_lat, tgt_lon, city_name=data.target_city
        )

        # 2️⃣ PGA predictions for the full magnitude range
        #    Returns list of dicts: {magnitude, pga_g, pga_cms2, is_input}
        pga_range = predict_pga_range(
            magnitude=data.magnitude,
            depth=data.depth,
            distance_km=distance_km,
            soil_type=soil_type
            # step=0.5, spread=1.0 are the defaults → gives ±1.0 in 0.5 steps
        )

        # 3️⃣ Damage analysis for every magnitude in the range
        #    Returns list of dicts: {magnitude, pga_g, pga_cms2, shaking_intensity,
        #                            damage_level, city_risk_pct, explanation,
        #                            recommended_actions, is_input}
        damage_range = analyze_damage_range(
            pga_range=pga_range,
            context={"target_city": data.target_city}
        )

        # 4️⃣ Cache the user's input magnitude entry for /download endpoints
        input_entry = next((r for r in damage_range if r["is_input"]), damage_range[2])
        try:
            city_risk_cache[data.target_city.lower()] = {
                "input": data.dict(),
                "pga": input_entry["pga_g"],
                "damage_level": input_entry["damage_level"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as cache_error:
            print(f"⚠ Cache update failed: {cache_error}")

        # 5️⃣ Build response
        return DamageRangeOutput(
            soil_type_used=soil_type,
            results=[
                DamageRangeItem(
                    magnitude=r["magnitude"],
                    pga_g=r["pga_g"],
                    pga_cms2=r["pga_cms2"],
                    shaking_intensity=r["shaking_intensity"],
                    damage_level=r["damage_level"],
                    city_risk_pct=r["city_risk_pct"],
                    explanation=r["explanation"],
                    recommended_actions=r["recommended_actions"],
                    is_input=r["is_input"]
                )
                for r in damage_range
            ]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
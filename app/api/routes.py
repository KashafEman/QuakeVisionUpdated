# # routes.py - COMPLETE UPDATED VERSION
# from fastapi import APIRouter, FastAPI, HTTPException
# from app.api import urban_planning
# from app.schemas.input_schema import EarthquakeInput
# from app.schemas.output_schema import DamageOutput
# from app.services.damage_analyzer.pga_predictor import predict_pga
# from app.services.damage_analyzer.analyze_damage import analyze_damage
# from app.utils.geocoding import get_city_coordinates, calculate_distance_km
# from app.utils.soil_inference import infer_soil_type

# app = FastAPI()
# router = APIRouter()


# @router.post("/predict-damage", response_model=DamageOutput)
# def predict_damage(data: EarthquakeInput):
#     try:
#         # 1️⃣ Geocoding & distance
#         epi_lat, epi_lon = get_city_coordinates(data.epicenter_city)
#         tgt_lat, tgt_lon = get_city_coordinates(data.target_city)
#         distance_km = calculate_distance_km(epi_lat, epi_lon, tgt_lat, tgt_lon)

#         soil_type = infer_soil_type(
#             tgt_lat, tgt_lon, city_name=data.target_city
#         )

#         # 2️⃣ PGA Prediction
#         pga_g, pga_cms2 = predict_pga(
#             magnitude=data.magnitude,
#             depth=data.depth,
#             distance_km=distance_km,
#             soil_type=soil_type
#         )

#         # 3️⃣ Damage logic (human-readable)
#         damage_context = {"target_city": data.target_city}
#         damage_result = analyze_damage(pga_g, damage_context)

#         # 4️⃣ INTERNAL analytics (NOT returned)
#         # Import inside function to avoid FastAPI schema issues
#         from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
#         from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
#         from app.services.damage_analyzer.risk_service import calculate_city_wide_risk
        
#         try:
#             vlm_result = get_damage_from_vlm(
#                 pga=pga_g,
#                 image_path="C:\\QuakeVision\\app\\static\\damage_curves.PNG"
#             )

#             # FIX: Use .dict() instead of .model_dump()
#             damage_5 = vlm_result.damage_estimates.dict()  # Changed from .model_dump()
            
#             damage_3 = map_to_pakistan_buildings(damage_5)

#             calculate_city_wide_risk(
#                 city_name=data.target_city,
#                 damage_ratios=damage_3
#             )
#         except Exception as vlm_error:
#             # Log but don't crash if VLM fails
#             print(f"VLM skipped: {vlm_error}")
#             # Use fallback estimates based on PGA
#             damage_3 = {
#                 "kacha": min(100, pga_g * 100),
#                 "semi_pacca": min(80, pga_g * 80),
#                 "pacca": min(40, pga_g * 40)
#             }
#             calculate_city_wide_risk(
#                 city_name=data.target_city,
#                 damage_ratios=damage_3
#             )

#         # 5️⃣ RESPONSE (schema-safe)
#         return DamageOutput(
#             pga=pga_g,
#             pga_cms2=pga_cms2,
#             damage_level=damage_result["damage_level"],
#             explanation=damage_result["explanation"],
#             recommended_actions=", ".join(damage_result["recommended_actions"]),
#             soil_type_used=soil_type
#         )

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# app.include_router(router)
# app.include_router(urban_planning.router)
from fastapi import APIRouter, FastAPI, HTTPException
from app.api import urban_planning
from app.api.state import city_risk_cache
from datetime import datetime
from app.schemas.input_schema import EarthquakeInput
from app.schemas.output_schema import DamageOutput
from app.services.damage_analyzer.pga_predictor import predict_pga
from app.services.damage_analyzer.analyze_damage import analyze_damage
from app.services.damage_analyzer.city_risk_pipeline import run_city_risk_pipeline
from app.utils.geocoding import get_city_coordinates, calculate_distance_km
from app.utils.soil_inference import infer_soil_type
from app.services.damage_analyzer.vlm_service import DamageEstimates # Then use: DamageEstimates(...)

app = FastAPI()
router = APIRouter()


@router.post("/predict-damage", response_model=DamageOutput)
def predict_damage(data: EarthquakeInput):
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

        # 3️⃣ FULL city risk pipeline (ONCE)
        try:
            city_risk_result = run_city_risk_pipeline(
                city_name=data.target_city,
                pga_g=pga_g
            )

            #  Cache for later download
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

        # Human-readable damage (API response)
        damage_result = analyze_damage(
            pga_g,
            {"target_city": data.target_city}
        )

        #  Return ONLY damage response
        return DamageOutput(
            pga=pga_g,
            pga_cms2=pga_cms2,
            damage_level=damage_result["damage_level"],
            explanation=damage_result["explanation"],
            recommended_actions=", ".join(
                damage_result["recommended_actions"]
            ),
            soil_type_used=soil_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(router)
app.include_router(urban_planning.router)
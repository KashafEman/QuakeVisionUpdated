from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Importing your existing logic
from app.services.damage_analyzer.pga_predictor import predict_pga
from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_sector_risk, sector_risk
from app.services.damage_analyzer.map_back import map_back_to_five_categories
from app.Urban_planning.recommendation_engine import generate_retrofit_plan
from app.Urban_planning.developer_recommendation_engine import developer_plan
from app.Urban_planning.retrofit_recommender_engine import retrofit_plan
from app.data.soil_map import get_soil_type_by_city

# Initialize the router for the Urban Planning module
router = APIRouter(
    prefix="/urban-planning",
    tags=["Urban Planning"]
)

# 1. Define the Input Schema (The "Request Body")
class RetrofitRequest(BaseModel):
    city_name: str
    sector_name: str
    material: str
    magnitude: float
    height: int

# 2. The API Endpoint
@router.post("/home-safety-retrofit")
async def home_safety_retrofit_guide(data: RetrofitRequest):
    try:
        # Step A: Get soil type for city
        soil_type = get_soil_type_by_city(data.city_name)
        # Step A: Get PGA Value
        pga_value, pga_cms2 = predict_pga(
            magnitude=data.magnitude, 
            depth=10.0, 
            distance_km=5.0, 
            soil_type=soil_type
        )
        # Step B: Get Damage Estimates from VLM
        # Note: Ensure "static/damage_curves.png" path is correct relative to your main.py
        image_path = "app\\static\\damage_curves.PNG"
        result = get_damage_from_vlm(pga_value, image_path)

        # Step C: Process Mappings
        estimates_dict = result.damage_estimates.dict()
        semi_final_mapping = map_to_pakistan_buildings(estimates_dict)

        # Step D: Risk Calculation and Final Categorization
        report = calculate_sector_risk(data.city_name, data.sector_name, semi_final_mapping)
        print(f"DEBUG: Type of report: {type(report)}")
        print(f"DEBUG: Report value: {report}")
        final_mapping = map_back_to_five_categories(report)
        print(f"DEBUG: Type of final_mapping: {type(final_mapping)}")
        print(f"DEBUG: Final mapping value: {final_mapping}")

        # Step E: Generate Retrofit Plan
        plan = generate_retrofit_plan(
            material=data.material,
            risk_map=final_mapping,
            magnitude=data.magnitude,
            height=data.height,
            allow_web=False
        )

        if "error" in plan:
            return {
                "status": "error",
                "message": plan["error"]
            }

        return {
            "status": "success",
            "pga_value": pga_value,
            "final_mapping": final_mapping,
            "ai_output": {
                "risk_assessment_summary": plan["risk_assessment_summary"],
                "action_recommendations": plan["action_recommendations"],
                "full_detailed_report": plan["full_detailed_report"],
                "web_content_summary": plan["web_content_summary"]
            }
        }

    except Exception as e:
        # If something goes wrong in the services, return a 500 error
        raise HTTPException(status_code=500, detail=str(e))
    

#-----------------------Private Developers--------------------------------

# 1. Define the Input Schema for Developers
class DeveloperPlanRequest(BaseModel):
    city_name: str
    site_sector: str
    project_type: str
    target_magnitude: float

# 2. The Developer API Endpoint
@router.post("/developer-site-planner")
async def developer_site_planner(data: DeveloperPlanRequest):
    try:
        # Step A: Get soil type for city
        soil_type = get_soil_type_by_city(data.city_name)
        # Step B: Seismic Data Fetching
        pga_value, pga_cms2 = predict_pga(
            magnitude=data.magnitude, 
            depth=10.0, 
            distance_km=5.0, 
            soil_type=soil_type
        )
        image_path = "app\\static\\damage_curves.PNG"

        # Step C: Damage Simulation
        vlm_result = get_damage_from_vlm(pga_value, image_path)
        damage_dict = vlm_result.damage_estimates.dict()

        # Step D: Mapping & Risk Calculation
        mapped_damage = map_to_pakistan_buildings(damage_dict)
        sector_risk_report = calculate_sector_risk(
            city_name=data.city_name,
            sector_name=data.site_sector,
            damage_ratios=mapped_damage
        )
        final_risk_map = map_back_to_five_categories(sector_risk_report)

       
        # Step E: AI Plan (now returns structured JSON)
        ai_recommendation = developer_plan(
            site_sector=data.site_sector,
            project_type=data.project_type,
            target_magnitude=data.target_magnitude,
            risk_map=final_risk_map,
            allow_web=True
        )

        # API fallback safety
        if "error" in ai_recommendation:
            return {
                "status": "error",
                "message": ai_recommendation["error"]
            }

       
        # Step E: Calculate Sustainability Score (Logic from your original script)
        survival_prob = round(100 - max(final_risk_map.values()), 2)

        # Instead of just a long string, we return a structured JSON response
        return {
            "status": "success",
            "metadata": {
                "project_type": data.project_type,
                "target_magnitude": data.target_magnitude,
                "site_sector": data.site_sector,
                "survival_probability": f"{survival_prob}%"
            },
            "risk_analysis": {
                "pga_predicted": f"{pga_value}g",
                "risk_map": final_risk_map
            },
            "ai_output": {
                "risk_assessment_summary": ai_recommendation["risk_assessment_summary"],
                "action_recommendations": ai_recommendation["action_recommendations"],
                "full_detailed_report": ai_recommendation["full_detailed_report"],
                "web_content_summary": ai_recommendation["web_content_summary"]
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable. Please try again later."
        )
    

#----------------------Regional Stretagist----------------------------



# 1. Define the Input Schema for Regional Strategy
class RegionalRetrofitRequest(BaseModel):
    city_name: str
    sector_name: str
    retrofit_capacity: int
    priority_metric: str  # e.g., "Save Maximum Lives", "Cost Effective"
    retrofit_style: str   # e.g., "Hybrid", "Traditional", "Modern"
    target_magnitude: float

# 2. The Regional Strategy API Endpoint
@router.post("/regional-retrofit-strategist")
async def regional_retrofit_strategist(data: RegionalRetrofitRequest):
    try:
        # Step A: Get soil type for city
        soil_type = get_soil_type_by_city(data.city_name)
        # Step B: Seismic Baseline
        pga_value, pga_cms2 = predict_pga(
            magnitude=data.magnitude, 
            depth=10.0, 
            distance_km=5.0, 
            soil_type=soil_type
        )
        image_path = "app\\static\\damage_curves.PNG"

        # Step C: Visual Language Model Damage Estimation
        result = get_damage_from_vlm(pga_value, image_path)
        estimates_dict = result.damage_estimates.dict()

        # Step D: Pakistan Building Context Mapping
        final_mapping = map_to_pakistan_buildings(estimates_dict)

        # Step E: Sector-Wide Risk Assessment
        # Using sector_risk as per your provided code
        report = sector_risk(data.city_name, data.sector_name, final_mapping)
        # Debug what sector_risk returns
        print(f"DEBUG: Type of report: {type(report)}")
        print(f"DEBUG: Report value: {report}")
        print(f"DEBUG: Is report a tuple? {isinstance(report, tuple)}")

        # Step F: Generate Strategic Action Plan
        action_plan = retrofit_plan(
            magnitude=data.target_magnitude,
            sector_data=report,
            retrofit_capacity=data.retrofit_capacity,
            priority_metric=data.priority_metric,
            retrofit_style=data.retrofit_style
        )

        if "error" in action_plan:
            return {
                "status": "error",
                "message": action_plan["error"]
            }

        return {
            "status": "success",
            "regional_context": {
                "city": data.city_name,
                "sector": data.sector_name,
                "predicted_pga": pga_value
            },
            "strategy_parameters": {
                "priority": data.priority_metric,
                "capacity_limit": data.retrofit_capacity,
                "style": data.retrofit_style
            },
            "risk_report": report,
            "ai_output": {
                "risk_assessment_summary": action_plan["risk_assessment_summary"],
                "action_recommendations": action_plan["action_recommendations"],
                "full_detailed_report": action_plan["full_detailed_report"],
                "web_content_summary": action_plan["web_content_summary"]
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regional Strategist Error: {str(e)}")
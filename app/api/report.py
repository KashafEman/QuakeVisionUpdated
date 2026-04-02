"""
api/routes/report.py
────────────────────
Report generation endpoints.

Flow:
  POST /api/v1/report/{home|gov|dev}
      → builds LangGraph state
      → runs full graph
      → saves resulting state to session store
      → returns ReportResponse
"""

import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from langchain_core.messages import HumanMessage

# ── Your project imports ──────────────────────────────────────────────────────
from app.agents.state import HomeQuery, GovQuery, DevQuery, create_initial_state
from app.agents.graph import app as quake_graph
from app.services.damage_analyzer.pga_predictor import predict_pga
from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_sector_risk, sector_risk
from app.services.damage_analyzer.map_back import map_back_to_five_categories
from app.data.soil_map import get_soil_type_by_city


# ── API layer imports ─────────────────────────────────────────────────────────
from app.schemas.input_schema import (
    HomeReportRequest, GovReportRequest, DevReportRequest,
)
from app.schemas.output_schema import (
    ReportResponse,
)
from app.api.session_store import save_session, cleanup_expired_sessions
# from api.auth import verify_api_key   # ❌ removed

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_report_response(session_id: str, user_type: str, result: dict) -> ReportResponse:
    final = result.get("final_output")
    if not final:
        raise HTTPException(status_code=500, detail="Graph ran but produced no final_output.")

    return ReportResponse(
        session_id=session_id,
        user_type=user_type,
        risk_assessment_summary=final.risk_assessment_summary or [],
        action_recommendations=final.action_recommendations or [],
        full_detailed_report=final.full_detailed_report or "",
        validation_score=final.validation_score or 0.0,
        is_validated=final.is_validated or False,
        validation_feedback=final.validation_feedback,
        visualization_data=result.get("visualization_data"),
        metadata=final.metadata or {},
        sources_used=final.sources_used or {},
        is_fallback=result.get("fallback_status") == "ACTIVE",
    )


async def _run_graph(state: dict, session_id: str, user_type: str) -> ReportResponse:
    try:
        result = await quake_graph.ainvoke(state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}")

    await save_session(session_id, result)
    return _build_report_response(session_id, user_type, result)


# ══════════════════════════════════════════════════════════════════════════════
# HOME ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/report/home", response_model=ReportResponse)
async def generate_home_report(
    body: HomeReportRequest,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(cleanup_expired_sessions)

    session_id = str(uuid.uuid4())
    soil_type =  get_soil_type_by_city(body.city_name)
    # Step A: Get PGA Value-----------------------------------------------------------
    pga_value, pga_cms2 = predict_pga(magnitude=body.magnitude, depth=10.0, distance_km=5.0, soil_type=soil_type)

    # Step B: Get Damage Estimates from VLM-------------------------------------------------------
    # Note: Ensure "static/damage_curves.png" path is correct relative to your main.py

    image_path = "app\static\damage_curves.PNG"

    result = get_damage_from_vlm(pga_value, image_path)

    # Step C: Process Mappings--------------------------------------------------------------------

    estimates_dict = result.damage_estimates.dict()
    semi_final_mapping = map_to_pakistan_buildings(estimates_dict)

    # Step D: Risk Calculation and Final Categorization---------------------------------------------

    report =   calculate_sector_risk(body.city_name, body.sector_name, semi_final_mapping)
    print(f"DEBUG: Type of report: {type(report)}")
    print(f"DEBUG: Report value: {report}")
    # final_mapping = {
    # "RCF": 5.95,
    # "RCI": 5.95,
    # "URM": 7.94,
    # "Adobe": 0.28,
    # "RubbleStone": 0.28
    # }    
    
    final_mapping = map_back_to_five_categories(report)
    print(f"DEBUG: Type of final_mapping: {type(final_mapping)}")
    print(f"DEBUG: Final mapping value: {final_mapping}")


    inputs = HomeQuery(
        magnitude=body.magnitude,
        material=body.material,
        risk_map= final_mapping,
        building_type=body.building_type,
        budget_level=body.budget_level,
        timeline_value=body.timeline_value,
        timeline_unit=body.timeline_unit,
        project_size_sqft=body.project_size_sqft,
        floors=body.floors,
        allow_web=body.allow_web,
    )

    state = create_initial_state(
        inputs=inputs,
        user_type="home",
        messages=[HumanMessage(content="Generate a seismic retrofit report for my home.")],
    )

    return await _run_graph(state, session_id, "home")


# ══════════════════════════════════════════════════════════════════════════════
# GOVERNMENT ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/report/gov", response_model=ReportResponse)
async def generate_gov_report(
    body: GovReportRequest,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(cleanup_expired_sessions)

    session_id = str(uuid.uuid4())
    # Step A: Get soil type for city-------------------
    soil_type = get_soil_type_by_city(body.city_name)


    # Step B: Seismic Baseline------------------------
    pga_value, pga_cms2 = predict_pga(
            magnitude=body.magnitude, 
            depth=10.0, 
            distance_km=5.0, 
            soil_type=soil_type
        )
        
    image_path = "app\static\damage_curves.PNG"

    # Step C: Visual Language Model Damage Estimation---------------------------
    result = get_damage_from_vlm(pga_value, image_path)
    
    estimates_dict = result.damage_estimates.dict()

    # Step D: Pakistan Building Context Mapping-------------------------------------------
    final_mapping = map_to_pakistan_buildings(estimates_dict)

    # Step E: Sector-Wide Risk Assessment---------------------------------------------
    # Using sector_risk as per your provided code
    # report = {
    #     "sector_name": body.sector_name,
    #     "total_buildings": 1000,
    #     "overall_percent": 55.0,
    #     "kacha_percent": 60,
    #     "semi_pacca_percent": 30,
    #     "pacca_percent": 10,
    #     "population": 30000
    # }  
    report = sector_risk(body.city_name, body.sector_name, final_mapping)
    # Debug what sector_risk returns
    print(f"DEBUG: Type of report: {type(report)}")
    print(f"DEBUG: Report value: {report}")
    print(f"DEBUG: Is report a tuple? {isinstance(report, tuple)}")

    inputs = GovQuery(
        magnitude=body.magnitude,
        sector_data=report,
        retrofit_capacity=body.retrofit_capacity,
        priority_metric=body.priority_metric,
        retrofit_style=body.retrofit_style,
        budget_level=body.budget_level,
        timeline_value=body.timeline_value,
        timeline_unit=body.timeline_unit,
        project_size_sqft=body.project_size_sqft,
        floors=body.floors,
        allow_web=body.allow_web,
    )

    state = create_initial_state(
        inputs=inputs,
        user_type="gov",
        messages=[HumanMessage(content="Generate a seismic retrofit action plan for our sector.")],
    )

    return await _run_graph(state, session_id, "gov")


# ══════════════════════════════════════════════════════════════════════════════
# DEVELOPER ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/report/dev", response_model=ReportResponse)
async def generate_dev_report(
    body: DevReportRequest,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(cleanup_expired_sessions)

    session_id = str(uuid.uuid4())
    soil_type = get_soil_type_by_city(body.city_name)
    #print(f"[Private Developer] Soil type for {body.city_name}: {soil_type}")
        # Step B: Seismic Data Fetching
    pga_value, pga_cms2 = predict_pga(
            magnitude=body.magnitude, 
            depth=10.0, 
            distance_km=5.0, 
            soil_type=soil_type
        )
    print(f"[Private Developer] Predicted PGA for {body.site_sector}: {pga_value}g")

    image_path = "app\static\damage_curves.PNG"

        # Step C: Damage Simulation
    vlm_result = get_damage_from_vlm(pga_value, image_path)

        

    print(vlm_result)
    # damage_dict = vlm_result.damage_estimates.model_dump()
    damage_dict = vlm_result.damage_estimates.dict()
    print(damage_dict)

    # Step D: Mapping & Risk Calculation
    mapped_damage = map_to_pakistan_buildings(damage_dict)

    print(mapped_damage)

    sector_risk_report = calculate_sector_risk(
            city_name=body.city_name,
            sector_name=body.site_sector,
            damage_ratios=mapped_damage
        )
        
    final_risk_map =  map_back_to_five_categories(sector_risk_report)

    inputs = DevQuery(
        magnitude=body.magnitude,
        site_sector=body.site_sector,
        project_type=body.project_type,
        risk_map=final_risk_map,
        project_name=body.project_name,
        building_type=body.building_type,
        budget_level=body.budget_level,
        timeline_value=body.timeline_value,
        timeline_unit=body.timeline_unit,
        project_size_sqft=body.project_size_sqft,
        floors=body.floors,
        allow_web=body.allow_web,
    )

    state = create_initial_state(
        inputs=inputs,
        user_type="dev",
        messages=[HumanMessage(content="Generate a seismic feasibility report for my development project.")],
    )

    return await _run_graph(state, session_id, "dev")
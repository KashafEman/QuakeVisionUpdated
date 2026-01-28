# # api/routes/risk.py
# from fastapi import APIRouter
# from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
# from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
# from app.services.damage_analyzer.risk_service import calculate_city_wide_risk

# router = APIRouter()

# @router.get("/cityRisk/{city_name}")

# def city_risk(city_name: str):

#     # Using default PGA value for demo
#     pga_value = 0.1
    
#     image_path = "app/static/damage_curves.png"

#     result = get_damage_from_vlm(pga_value, image_path)

#     print("Damage percentages:")
#     print(result)


#     # Convert the Pydantic object to a standard Python dictionary for your mapping service
#     estimates_dict = result.damage_estimates.model_dump()

#     final_mapping = map_to_pakistan_buildings(estimates_dict)


#     print("--- Final Mapping for Pakistan Context ---")
#     print(final_mapping)

#     risk_report = calculate_city_wide_risk(city_name, final_mapping)

#     return {
#         "status": "success",
#         "city": city_name,
#         "pga_used": pga_value,
#         "vlm_raw_estimates": estimates_dict,
#         "pakistan_context_mapping": final_mapping,
#         "risk_summary": risk_report['city_summary'],
#         "detailed_sectors": risk_report['detailed_sectors']
#     }


# #http://127.0.0.1:8000/cityRisk/Islamabad
# #uvicorn api.routes.risk:app --reload
from fastapi import APIRouter, HTTPException
from app.api.state import city_risk_cache
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_city_wide_risk

router = APIRouter()


@router.get("/cityRisk/{city_name}")
def city_risk(city_name: str):
    """
    Generate city-wide earthquake risk report
    using previously computed damage analysis.
    """

    city_key = city_name.strip().lower()

    #  Check if prior analysis exists
    if city_key not in city_risk_cache:
        raise HTTPException(
            status_code=400,
            detail="No prior damage analysis found. Run /predict-damage first."
        )

    stored = city_risk_cache[city_key]

    #  Extract stored values
    pga_value = stored["pga"]
    damage_estimates = stored.get("damage_estimates")

    if not damage_estimates:
        raise HTTPException(
            status_code=500,
            detail="Stored damage estimates missing or corrupted."
        )

    # Map to Pakistan building context
    pakistan_mapping = map_to_pakistan_buildings(damage_estimates)

    #  Calculate city-wide risk
    risk_report = calculate_city_wide_risk(city_name, pakistan_mapping)

    return {
        "status": "success",
        "city": city_name,
        "based_on_analysis": {
            "pga": pga_value,
            "pga_formatted": f"{pga_value:.4f}g",
            "damage_level": stored.get("damage_level"),
            "timestamp": stored.get("timestamp"),
        },
        "pakistan_context_mapping": pakistan_mapping,
        "risk_summary": risk_report.get("city_summary", {}),
        "detailed_sectors": risk_report.get("detailed_sectors", [])
    }

    
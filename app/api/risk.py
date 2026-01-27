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
from app.services.damage_analyzer.vlm_service import get_damage_from_vlm
from app.services.damage_analyzer.maping_service import map_to_pakistan_buildings
from app.services.damage_analyzer.risk_service import calculate_city_wide_risk

def run_city_risk_pipeline(city_name: str, pga_g: float):
    """
    Full city risk pipeline.
    Called internally after PGA prediction.
    """

    # 1️⃣ VLM damage estimation
    vlm_result = get_damage_from_vlm(
        pga=pga_g,
        image_path="C:\\QuakeVision\\app\\static\\damage_curves.PNG"
    )

    damage_5 = vlm_result.damage_estimates.dict()

    # 2️⃣ Pakistan-specific mapping
    damage_3 = map_to_pakistan_buildings(damage_5)

    # 3️⃣ City-wide risk calculation (Firebase inside)
    risk_report = calculate_city_wide_risk(
        city_name=city_name,
        damage_ratios=damage_3
    )

    # Return BOTH risk report AND damage estimates
    return {
        "risk_report": risk_report,
        "damage_estimates": damage_5,  # Add this
        "damage_estimates_mapped": damage_3  # Optional: also include mapped version
    }
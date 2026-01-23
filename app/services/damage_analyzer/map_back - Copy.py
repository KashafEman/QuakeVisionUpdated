# services/map_back_service.py

def map_back_to_five_categories(sector_risk):
    """
    Takes sector risk output and converts 3-category percentages
    back into 5 building categories.

    Input: sector_risk dict from calculate_sector_risk
    Output: dict with RCF, RCI, URM, Adobe, RubbleStone (%)
    """

    kacha = sector_risk["kacha_percent"]
    semi_pacca = sector_risk["semi_pacca_percent"]
    pacca = sector_risk["pacca_percent"]

    # Split logic (equal distribution)
    adobe = kacha 
    rubble_stone = kacha 

    urm = semi_pacca

    rcf = pacca 
    rci = pacca 

    return {
        "RCF": round(rcf, 2),
        "RCI": round(rci, 2),
        "URM": round(urm, 2),
        "Adobe": round(adobe, 2),
        "RubbleStone": round(rubble_stone, 2)
    }


# sector_result = {
#     "overall_percent": 20.4,
#     "kacha_percent": 0.56,
#     "semi_pacca_percent": 7.94,
#     "pacca_percent": 11.9
# }

# mapped_back = map_back_to_five_categories(sector_result)

# print("\n--- Mapped Back to 5 Building Types ---")
# for k, v in mapped_back.items():
#     print(f"{k:12}: {v}%")

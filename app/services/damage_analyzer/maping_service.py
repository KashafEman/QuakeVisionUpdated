# services/mapping_service.py

# services/mapping_service.py

def map_to_pakistan_buildings(damage_dict):
    # Helper to convert "51%" or 51 to float 51.0
    def clean_val(val):
        if isinstance(val, str):
            return float(val.replace('%', '').strip())
        return float(val)

    # Clean the input data
    data = {k: clean_val(v) for k, v in damage_dict.items()}

    # Perform the calculations
    kacha = (data["Adobe"] + data["RubbleStone"]) / 2
    semi_pacca = data["URM"]
    pacca = (data["RCF"] + data["RCI"]) / 2

    return {
        "kacha": round(kacha, 2),
        "semi_pacca": round(semi_pacca, 2),
        "pacca": round(pacca, 2)
    }

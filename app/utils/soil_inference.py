from app.data.soil_map import KNOWN_CITY_SOILS
from app.utils.geocoding import calculate_distance_km
from collections import Counter

def infer_soil_type(lat: float, lon: float, city_name: str | None = None, k: int = 3) -> str:
    """
    Infer soil type.
    - If city exists in KNOWN_CITY_SOILS → return its soil
    - Otherwise → infer from nearest k cities
    """

   
    if city_name:
        for entry in KNOWN_CITY_SOILS:
            if entry["city"].lower() == city_name.lower():
                return entry["soil"]

    # 2️⃣ Nearest-city inference
    distances = []

    for entry in KNOWN_CITY_SOILS:
        d = calculate_distance_km(lat, lon, entry["lat"], entry["lon"])
        distances.append((d, entry["soil"]))

    distances.sort(key=lambda x: x[0])

    nearest_soils = [soil for _, soil in distances[:k]]

    most_common = Counter(nearest_soils).most_common(1)

    return most_common[0][0]

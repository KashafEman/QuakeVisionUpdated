import requests
import math

def get_city_coordinates(city_name: str, country: str = "Pakistan"):
    """
    Get latitude and longitude of a city using OpenStreetMap Nominatim API.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{city_name}, {country}",
        "format": "json",
        "limit": 1
    }
    response = requests.get(url, params=params, headers={"User-Agent": "quakevision-app"})
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"City '{city_name}' not found")
    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    return lat, lon

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Compute distance between two coordinates using Haversine formula.
    Returns distance in km.
    """
    R = 6371  # Earth radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

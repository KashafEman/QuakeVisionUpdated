import requests

def get_city_coordinates(city_name: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1
    }
    response = requests.get(url, params=params)
    data = response.json()
    if not data:
        raise ValueError(f"City '{city_name}' not found")
    return float(data[0]['lat']), float(data[0]['lon'])

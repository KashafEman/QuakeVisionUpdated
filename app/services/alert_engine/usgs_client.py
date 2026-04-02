import requests
from typing import List, Dict
from .config import USGS_FEED_URL


def fetch_usgs_feed() -> Dict:
    response = requests.get(USGS_FEED_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_earthquakes(data: Dict) -> List[Dict]:
    earthquakes = []

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])

        if props.get("mag") is None or len(coords) < 2:
            continue

        earthquakes.append({
            "usgs_id": feature.get("id"),
            "magnitude": props.get("mag"),
            "location": props.get("place"),
            "timestamp": props.get("time"),
            "lat": coords[1],
            "lng": coords[0],
        })

    return earthquakes

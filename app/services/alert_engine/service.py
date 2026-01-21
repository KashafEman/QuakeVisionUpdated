from .config import MIN_MAGNITUDE, PAKISTAN_BOUNDS
from .usgs_client import fetch_usgs_feed, parse_earthquakes
from .repository import save_alert, alert_exists
from app.services.alert_engine.notification import send_push_notification  # Firebase Cloud Messaging wrapper

def is_within_pakistan(lat: float, lng: float) -> bool:
    return (
        PAKISTAN_BOUNDS["min_lat"] <= lat <= PAKISTAN_BOUNDS["max_lat"]
        and PAKISTAN_BOUNDS["min_lng"] <= lng <= PAKISTAN_BOUNDS["max_lng"]
    )

def process_usgs_feed() -> None:
    """
    Fetch USGS feed, filter earthquakes by magnitude and location,
    save new alerts to Firestore, and send push notifications to users.
    """
    data = fetch_usgs_feed()
    earthquakes = parse_earthquakes(data)

    for quake in earthquakes:
        # Skip small quakes
        if quake["magnitude"] < MIN_MAGNITUDE:
            continue

        # Skip quakes outside Pakistan
        if not is_within_pakistan(quake["lat"], quake["lng"]):
            continue

        # Avoid duplicates
        if alert_exists(quake["id"]):
            continue

        # Save to Firestore
        save_alert(quake)

        # Send push notification
        message = (
            f"Earthquake Alert!\nLocation: {quake['place']}\n"
            f"Magnitude: {quake['magnitude']}\nTime: {quake['time']}"
        )
        send_push_notification(message)

# app/services/alert_engine/repository.py
from firebase_admin import firestore
from .severity import calculate_severity
from datetime import datetime

def get_db():
    """Return Firestore client after Firebase initialized."""
    return firestore.client()


def alert_exists(usgs_id: str) -> bool:
    db = get_db()
    query = (
        db.collection("alerts")
        .where("usgs_id", "==", usgs_id)
        .limit(1)
        .stream()
    )
    return any(query)


def save_alert(quake: dict) -> None:
    db = get_db()
    if alert_exists(quake["usgs_id"]):
        return

    alert = {
        "usgs_id": quake["usgs_id"],
        "magnitude": quake["magnitude"],
        "location": quake["location"],
        "severity": calculate_severity(quake["magnitude"]),
        "lat": quake["lat"],
        "lng": quake["lng"],
        "timestamp": datetime.utcfromtimestamp(quake["timestamp"] / 1000),
    }

    db.collection("alerts").add(alert)

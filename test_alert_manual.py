from app.init_firebase import init_firebase
from app.services.alert_engine.repository import save_alert

# Initialize Firestore
db = init_firebase()

# Dummy earthquake data
dummy_quake = {
    "usgs_id": "TEST1234",
    "magnitude": 6.2,
    "location": "Karachi, Pakistan",
    "lat": 24.8607,
    "lng": 67.0011,
    "timestamp": 1700000000000  # UNIX timestamp in milliseconds
}

# Save to Firestore
save_alert(dummy_quake)
print("Dummy earthquake alert saved to Firestore.")

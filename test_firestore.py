# test_firestore.py
from app.init_firebase import init_firebase

# Initialize Firebase
db = init_firebase()

# Fetch all alerts
alerts = list(db.collection("alerts").stream())

for alert in alerts:
    print(alert.to_dict())

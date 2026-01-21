from fastapi import FastAPI
from app.api.routes import router
from app.services.alert_engine.scheduler import start_scheduler
from app import init_firebase
from firebase_admin import firestore 
from app.init_firebase import init_firebase

app = FastAPI(
    title="Quake Vision Backend",
    description="PGA Prediction + Damage Assessment API",
    version="1.0.0"
)

# Initialize Firebase
init_firebase()

# 🔴 TEMPORARY FIREBASE TEST
db = firestore.client()
db.collection("test").add({"status": "firebase connected"})

app.include_router(router)
start_scheduler(app)

@app.get("/")
def root():
    return {"status": "Quake Vision backend running"}

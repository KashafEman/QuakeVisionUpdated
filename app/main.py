from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Quake Vision Backend",
    description="PGA Prediction + Damage Assessment API",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def root():
    return {"status": "Quake Vision backend running"}

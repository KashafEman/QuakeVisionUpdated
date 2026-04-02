from fastapi import FastAPI
from app.api.routes import router
from app.services.alert_engine.scheduler import start_scheduler
from fastapi.middleware.cors import CORSMiddleware
from app import init_firebase
from firebase_admin import firestore 
from app.init_firebase import init_firebase
from app.api.risk import router as risk_router
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from app.api import report, chat, health

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 QuakeVision AI API starting up...")
    yield
    print("🛑 QuakeVision AI API shutting down...")



app = FastAPI(
    title="QuakeVision AI",
    description="Seismic Retrofit Analysis & Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize Firebase
init_firebase()

db = firestore.client()
db.collection("test").add({"status": "firebase connected"})

app.include_router(router)
app.include_router(risk_router)
app.include_router(health.router,  tags=["Health"])
app.include_router(report.router,  prefix="/api/v1", tags=["Report Generation"])
app.include_router(chat.router,    prefix="/api/v1", tags=["Chatbot"])
start_scheduler(app)

@app.get("/")
def root():
    return {"status": "Quake Vision backend running"}
@app.get("/test")
def test_api():
    return {"message": "Backend connected successfully!"}

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    schema["components"]["securitySchemes"] = {
        "ApiKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    # Apply globally so every endpoint shows the lock icon in /docs
    schema["security"] = [{"ApiKeyHeader": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
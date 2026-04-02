from fastapi import APIRouter, Request
from app.api.session_store import active_session_count
import os

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "QuakeVision AI"}


@router.get("/health/sessions")
async def session_stats():
    return {
        "active_sessions": active_session_count(),
        "status": "ok"
    }


@router.get("/health/debug-key")
async def debug_key(request: Request):
    """TEMPORARY - remove after fixing auth"""
    raw = os.getenv("API_KEYS", "NOT FOUND")
    incoming = request.headers.get("X-API-Key", "NO HEADER SENT")
    return {
        "env_raw": repr(raw),           # shows spaces/hidden chars
        "env_keys_parsed": list({k.strip() for k in raw.split(",") if k.strip()}),
        "incoming_header": repr(incoming),
        "match": incoming.strip() in {k.strip() for k in raw.split(",") if k.strip()}
    }

#Save, restart uvicorn, then hit this in your browser:

#http://localhost:8000/health/debug-key
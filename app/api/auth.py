#API key verification

"""
api/auth.py
───────────
API key authentication for all endpoints.

Keys are stored in .env as a comma-separated list:
    API_KEYS=key1,key2,key3

Pass the key in every request:
  • HTTP header:  X-API-Key: your-key
  • WebSocket:    ws://host/chat/ws/{session_id}?api_key=your-key
"""

import os
from fastapi import Header, Query, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery

# ── Load valid keys from environment ─────────────────────────────────────────
def _load_keys() -> set:
    raw = os.getenv("API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    if not keys:
        keys = {"dev-secret-key"}
    return keys


VALID_KEYS: set = _load_keys()

# FastAPI security schemes (used for /docs Authorize button)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query  = APIKeyQuery(name="api_key",    auto_error=False)   # for WS


def verify_api_key(
    header_key: str | None = Security(api_key_header),
    query_key:  str | None = Security(api_key_query),
) -> str:
    """
    FastAPI dependency — inject with `Depends(verify_api_key)`.
    Checks header first, then query param (needed for WebSocket URLs).
    Raises 401 if no valid key is found.
    """
    key = header_key or query_key
    if key and key in VALID_KEYS:
        return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key. Pass X-API-Key header.",
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def verify_ws_api_key(api_key: str = Query(...)) -> str:
    """
    Standalone dependency for WebSocket routes (query-param only).
    Usage:  ws://host/chat/ws/{session_id}?api_key=YOUR_KEY
    """
    if api_key in VALID_KEYS:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )
#holds LangGraph state between requests

"""
api/session_store.py
────────────────────
In-memory session store that holds LangGraph AgentState between HTTP / WS calls.

Each session is keyed by a UUID (session_id) returned to the frontend at report
generation time. The frontend sends this ID with every subsequent chat request.

For production you can swap this for Redis using the same interface.
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta

# session_id → {"state": AgentState, "last_active": datetime}
_store: Dict[str, dict] = {}
_lock = asyncio.Lock()

SESSION_TTL_MINUTES = 120   # sessions expire after 2 hours of inactivity


async def save_session(session_id: str, state: dict) -> None:
    async with _lock:
        _store[session_id] = {
            "state": state,
            "last_active": datetime.utcnow(),
        }


async def get_session(session_id: str) -> Optional[dict]:
    async with _lock:
        entry = _store.get(session_id)
        if entry is None:
            return None
        # Touch last_active
        entry["last_active"] = datetime.utcnow()
        return entry["state"]


async def delete_session(session_id: str) -> None:
    async with _lock:
        _store.pop(session_id, None)


async def cleanup_expired_sessions() -> int:
    """Remove sessions older than SESSION_TTL_MINUTES. Call periodically."""
    cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TTL_MINUTES)
    removed = 0
    async with _lock:
        expired = [sid for sid, entry in _store.items() if entry["last_active"] < cutoff]
        for sid in expired:
            del _store[sid]
            removed += 1
    return removed


def active_session_count() -> int:
    return len(_store)
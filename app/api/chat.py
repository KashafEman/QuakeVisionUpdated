"""
api/routes/chat.py
──────────────────
Chatbot endpoints — WebSocket (primary) + REST (fallback)
"""

import json
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from app.agents.nodes import chatbot_node

from app.schemas.input_schema import ChatMessageRequest
from app.schemas.output_schema import ChatResponse
from app.api.session_store import get_session, save_session, delete_session

# from api.auth import verify_api_key, verify_ws_api_key   # ❌ removed

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# SHARED CORE — one chatbot turn
# ══════════════════════════════════════════════════════════════════════════════

async def _chat_turn(session_id: str, user_message: str) -> dict:
    state = await get_session(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{session_id}' not found or expired. "
                "Generate a report first via POST /api/v1/report/{type}."
            ),
        )

    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=user_message))
    state = {**state, "messages": messages}

    result = await chatbot_node(state)

    await save_session(session_id, {**state, **result})

    bot_messages = result.get("messages", [])
    if bot_messages:
        last = bot_messages[-1]
        raw_content = last.content if hasattr(last, "content") else str(last)
    else:
        raw_content = json.dumps({
            "ui_type": "message",
            "message": "No response.",
            "data": {}
        })

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        parsed = {"ui_type": "message", "message": raw_content, "data": {}}

    return {
        "parsed": parsed,
        "chatbot_status": result.get("chatbot_response", "CONTINUE"),
    }


def _envelope(parsed: dict, status: str) -> dict:
    return {
        "ui_type":        parsed.get("ui_type", "message"),
        "message":        parsed.get("message", ""),
        "data":           parsed.get("data", {}),
        "chatbot_status": status,
    }


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════

@router.websocket("/chat/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()

    if await get_session(session_id) is None:
        await websocket.send_json({
            "ui_type": "error",
            "message": f"Session '{session_id}' not found. Generate a report first.",
            "data": {},
            "chatbot_status": "ERROR",
        })
        await websocket.close(code=1008)
        return

    # Auto-send initial options card
    try:
        init = await _chat_turn(session_id, "start")
        await websocket.send_json(_envelope(init["parsed"], init["chatbot_status"]))
    except Exception as exc:
        await websocket.send_json({
            "ui_type": "error",
            "message": f"Failed to initialize chatbot: {exc}",
            "data": {},
            "chatbot_status": "ERROR",
        })
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                payload = json.loads(raw)
                user_message = payload.get("message", "").strip()
            except json.JSONDecodeError:
                user_message = raw.strip()

            if not user_message:
                continue

            try:
                turn   = await _chat_turn(session_id, user_message)
                status = turn["chatbot_status"]

                await websocket.send_json(_envelope(turn["parsed"], status))

                if status == "END_CONVERSATION":
                    await delete_session(session_id)
                    await websocket.close()
                    break

            except HTTPException as he:
                await websocket.send_json({
                    "ui_type": "error",
                    "message": he.detail,
                    "data": {},
                    "chatbot_status": "ERROR",
                })
            except Exception as exc:
                await websocket.send_json({
                    "ui_type": "error",
                    "message": f"Server error: {exc}",
                    "data": {},
                    "chatbot_status": "ERROR",
                })

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected — session {session_id} preserved.")


# ══════════════════════════════════════════════════════════════════════════════
# REST FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/chat/message", response_model=ChatResponse)
async def chat_message(
    body: ChatMessageRequest,
):
    turn   = await _chat_turn(body.session_id, body.message)
    parsed = turn["parsed"]
    status = turn["chatbot_status"]

    if status == "END_CONVERSATION":
        await delete_session(body.session_id)

    return ChatResponse(
        session_id=body.session_id,
        ui_type=parsed.get("ui_type", "message"),
        message=parsed.get("message", ""),
        data=parsed.get("data", {}),
        chatbot_status=status,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SESSION UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/chat/session/{session_id}")
async def get_session_info(
    session_id: str,
):
    state = await get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    return {
        "session_id":             session_id,
        "user_type":              state.get("user_type"),
        "is_validated":           state.get("is_validated", False),
        "validation_score":       state.get("validation_score"),
        "in_chat_mode":           state.get("in_chat_mode", False),
        "has_visualization":      state.get("visualization_data") is not None,
        "has_regenerated_report": state.get("regenerated_report") is not None,
        "active_report":          state.get("active_report", "original"),
        "message_count":          len(state.get("messages", [])),
        "is_fallback":            state.get("fallback_status") == "ACTIVE",
    }


@router.delete("/chat/session/{session_id}")
async def end_session(
    session_id: str,
):
    await delete_session(session_id)
    return {"session_id": session_id, "status": "deleted"}
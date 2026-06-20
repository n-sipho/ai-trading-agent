"""
FastAPI Backend — Conversational MT5 SMC Trading Assistant.

Exposes:
- WebSocket ``/ws/chat``  → real-time chat with the Pydantic AI agent
- GET      ``/api/health`` → liveness check
- GET      ``/api/account`` → trigger the agent to summarise account info
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent import run_agent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MT5 SMC Trading Assistant",
    description="Conversational trading assistant powered by Pydantic AI + MetaTrader 5 MCP",
    version="1.0.0",
)

# CORS — wide open for development; lock down in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _ws_response(content: str) -> str:
    """Build a JSON response message for the WebSocket."""
    return json.dumps({
        "type": "response",
        "content": content,
        "timestamp": _now_iso(),
    })


def _ws_loading(is_loading: bool) -> str:
    """Build a JSON loading-state message for the WebSocket."""
    return json.dumps({
        "type": "loading",
        "isLoading": is_loading,
    })


def _ws_error(message: str) -> str:
    """Build a JSON error message for the WebSocket."""
    return json.dumps({
        "type": "error",
        "content": message,
        "timestamp": _now_iso(),
    })


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health_check():
    """Simple liveness / readiness probe."""
    return {
        "status": "healthy",
        "service": "mt5-smc-assistant",
        "timestamp": _now_iso(),
    }


@app.get("/api/account")
async def get_account_info():
    """Ask the agent to fetch and summarise MT5 account information."""
    try:
        response = await run_agent(
            "Get my account information and summarize the balance, equity, "
            "margin, free margin, and any open positions."
        )
        return {
            "status": "ok",
            "data": response,
            "timestamp": _now_iso(),
        }
    except Exception as exc:
        logger.exception("Failed to fetch account info")
        return {
            "status": "error",
            "message": str(exc),
            "timestamp": _now_iso(),
        }


# ---------------------------------------------------------------------------
# WebSocket Chat Endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Handle a real-time chat session with the SMC trading assistant.

    Protocol
    --------
    **Client → Server** (JSON):
        ``{"type": "message", "content": "user text here"}``

    **Server → Client** (JSON):
        ``{"type": "loading",  "isLoading": true | false}``
        ``{"type": "response", "content": "...", "timestamp": "..."}``
        ``{"type": "error",    "content": "...", "timestamp": "..."}``
    """
    await ws.accept()
    logger.info("WebSocket client connected")

    # Per-connection conversation history for multi-turn context
    message_history: list = []

    try:
        while True:
            # Wait for the next message from the client
            raw = await ws.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(_ws_error("Invalid JSON payload."))
                continue

            msg_type = data.get("type")
            content = data.get("content", "").strip()

            if msg_type != "message" or not content:
                await ws.send_text(_ws_error("Expected {\"type\": \"message\", \"content\": \"...\"}"))
                continue

            logger.info("User message: %s", content[:120])

            # Signal that the agent is working
            await ws.send_text(_ws_loading(True))

            try:
                # Run the agent
                response_text = await run_agent(content, message_history)

                # Send the response
                await ws.send_text(_ws_response(response_text))

            except Exception as exc:
                logger.exception("Agent error during WebSocket chat")
                await ws.send_text(_ws_error(f"Agent error: {exc}"))

            finally:
                # Always clear the loading state
                await ws.send_text(_ws_loading(False))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.exception("Unexpected WebSocket error")
        try:
            await ws.send_text(_ws_error(f"Server error: {exc}"))
        except Exception:
            pass

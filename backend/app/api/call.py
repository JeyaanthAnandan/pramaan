"""Call Pramaan: the WebSocket a voice call runs on (see app/agents/call.py).

Binary frames from the browser are microphone audio (PCM16, 16 kHz, mono); binary frames to the
browser are the agent's voice (PCM16, 24 kHz). Text frames are JSON events: captions, the figures
the agent said (each opens the Evidence Lens), screen actions, interruptions, the end of the call.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import access
from app.agents.call import LANGS, CallContext, bridge
from app.api.routes import ai_allow, client_ip
from app.config import settings
from app.evidence.store import store

log = logging.getLogger("pramaan.call")
router = APIRouter(prefix="/api")


def _same_site(ws: WebSocket) -> bool:
    """Only our own page may open a call (the project cookie would otherwise ride along)."""
    origin = ws.headers.get("origin")
    if not origin:
        return True  # not a browser
    host = urlparse(origin).hostname or ""
    return urlparse(origin).netloc == ws.headers.get("host") or host in {"localhost", "127.0.0.1"}


async def _refuse(ws: WebSocket, code: str, close: int) -> None:
    await ws.send_json({"type": "error", "code": code})
    await ws.close(code=close)


@router.websocket("/projects/{pid}/call")
async def call(ws: WebSocket, pid: str, lang: str = "en") -> None:
    await ws.accept()
    if not _same_site(ws):
        return await _refuse(ws, "origin", 4403)
    p = store().get_project(pid)
    if p is None:
        return await _refuse(ws, "not_found", 4404)
    if not access.allowed(pid, ws.cookies.get(access.cookie_name(pid))):
        return await _refuse(ws, "private", 4401)
    if not settings().gemini_configured:
        return await _refuse(ws, "no_gemini", 4503)
    result = store().get_latest_result(pid)
    if result is None:
        return await _refuse(ws, "no_report", 4409)
    if "operations" not in result:
        from app.agents.workflow import recalculate

        result = recalculate(pid)
    if not ai_allow(client_ip(ws.headers.get("x-forwarded-for", ""), ws.client.host if ws.client else None), "call"):
        return await _refuse(ws, "rate_limited", 4429)
    try:
        await bridge(ws, CallContext.build(p, result), lang if lang in LANGS else "en")
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.exception("call failed")
        try:
            await ws.send_json({"type": "error", "code": "call_failed", "detail": str(exc)[:200] or exc.__class__.__name__})
        except Exception:  # noqa: S110 - the caller may already be gone
            pass
    try:
        await ws.close()
    except Exception:  # noqa: S110 - already closed
        pass

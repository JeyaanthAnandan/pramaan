"""Project passcodes: an exporter's own project (bills, invoices, production data) is private.

Creating a project returns a passcode once (shown to the owner to open the project on another
device) and sets an HttpOnly cookie scoped to /api/projects/{pid}, so the browser that created it
needs nothing else. Only a SHA-256 hash is stored. Fictional sample copies stay open, and buyer
links (/api/share/{token}) never need a passcode: they show the summary only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request, Response

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L: easy to read out and type on a phone
COOKIE_DAYS = 30
_cache: dict[str, tuple[str | None, float]] = {}
_CACHE_S = 30.0


def new_passcode() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_code(pid: str, code: str) -> str:
    return hashlib.sha256(f"pramaan:{pid}:{normalize(code)}".encode()).hexdigest()


def matches(pid: str, access_hash: str, code: str | None) -> bool:
    return bool(code) and hmac.compare_digest(hash_code(pid, code or ""), access_hash)


def cookie_name(pid: str) -> str:
    return f"pk_{pid}"


def set_cookie(request: Request, response: Response, pid: str, code: str) -> None:
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(
        cookie_name(pid),
        normalize(code),
        max_age=COOKIE_DAYS * 86400,
        path=f"/api/projects/{pid}",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def forget(pid: str) -> None:
    _cache.pop(pid, None)


def _hash_for(pid: str) -> str | None:
    hit = _cache.get(pid)
    if hit and time.monotonic() - hit[1] < _CACHE_S:
        return hit[0]
    from app.evidence.store import store

    p = store().get_project(pid)
    h = p.access_hash if p else None
    if p is not None:
        _cache[pid] = (h, time.monotonic())
    return h


async def require(request: Request) -> None:
    """Router dependency: every /api/projects/{pid}/... call needs the project's passcode (cookie or
    X-Pramaan-Key header) when the project has one."""
    pid = request.path_params.get("pid")
    if not pid or request.url.path.endswith("/unlock"):
        return
    if not allowed(pid, request.cookies.get(cookie_name(pid)) or request.headers.get("x-pramaan-key")):
        raise HTTPException(401, "This project is private: enter its passcode.")


def allowed(pid: str, code: str | None) -> bool:
    """True for an open project (fictional sample copies) or the right passcode. Shared by the HTTP
    routes and the voice-call WebSocket, which has no Request to raise on."""
    h = _hash_for(pid)
    return not h or matches(pid, h, code)

"""The Gemini wrapper falls back from the Interactions API to models.generate_content when the
endpoint is not served for the project, keeping schema, thinking level and media resolution."""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from typing import Any

from app.agents import llm


class _Interactions:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **body: Any) -> Any:
        self.calls += 1
        raise RuntimeError("404 NOT_FOUND: interactions is not available for this endpoint")


class _Models:
    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []

    async def generate_content(self, model: str, contents: Any, config: Any) -> Any:
        self.seen.append({"model": model, "config": config, "contents": contents})
        return SimpleNamespace(
            text=json.dumps({"doc_type": "gas_invoice"}),
            usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5, thoughts_token_count=2),
        )


def _gemini() -> llm.Gemini:
    g = llm.Gemini.__new__(llm.Gemini)
    g._sem = asyncio.Semaphore(4)
    g.use_interactions = True
    g.client = SimpleNamespace(aio=SimpleNamespace(interactions=_Interactions(), models=_Models()))
    return g


def test_json_falls_back_to_generate_content() -> None:
    g = _gemini()
    parts = [llm.text_part("classify"), llm.image_part(b"\xff\xd8\xff", "image/jpeg", "high")]
    r = asyncio.run(g.json("gemini-3.8-flash", "sys", parts, {"type": "object"}, thinking_level="low"))
    assert r.data == {"doc_type": "gas_invoice"} and r.tokens_in == 10 and r.tokens_out == 7
    assert g.use_interactions is False
    cfg = g.client.aio.models.seen[0]["config"]
    assert cfg.response_json_schema == {"type": "object"} and cfg.response_mime_type == "application/json"
    assert str(cfg.thinking_config.thinking_level).endswith("LOW") and str(cfg.media_resolution).endswith("HIGH")
    assert cfg.temperature is None  # never set
    # second call goes straight to generate_content
    asyncio.run(g.json("gemini-3.8-flash", "sys", parts, {"type": "object"}))
    assert g.client.aio.interactions.calls == 1


def test_transcribe_fallback_uses_flash_audio() -> None:
    g = _gemini()
    audio = {"type": "audio", "data": base64.b64encode(b"x").decode(), "mime_type": "audio/webm"}
    r = asyncio.run(g.transcribe("gemini-3.5-transcribe", audio, {"mode": {"type": "smart"}}))
    assert g.client.aio.models.seen[0]["model"] == "gemini-3.8-flash" and r.model == "gemini-3.8-flash"

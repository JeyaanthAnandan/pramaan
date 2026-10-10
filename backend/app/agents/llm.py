"""Gemini access through the google-genai Interactions API.

Production: Gemini Enterprise Agent Platform (Vertex mode) with the Cloud Run service
account, location ``global`` (3.8 Flash / 3.5 Flash-Lite are served from global/us/eu).
Local: Gemini Developer API with GEMINI_API_KEY from .env.local.

Rules from the brief: only Gemini 3.x models, never set temperature/top_p/top_k, high media
resolution for document images, JSON output validated with Pydantic by the caller.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings

FORBIDDEN_PREFIXES = ("gemini-1", "gemini-2", "veo-", "deep-research")


@dataclass
class LLMResult:
    data: Any
    model: str
    tokens_in: int | None
    tokens_out: int | None
    duration_ms: int
    raw_text: str = ""


class LLMUnavailable(RuntimeError):
    pass


def _check_model(model: str) -> None:
    if model.startswith(FORBIDDEN_PREFIXES):
        raise ValueError(f"model {model} is not allowed (Gemini 2.x / Veo / deep-research are forbidden)")


def image_part(data: bytes, mime: str = "image/jpeg", resolution: str = "high") -> dict[str, Any]:
    return {"type": "image", "data": base64.b64encode(data).decode(), "mime_type": mime, "resolution": resolution}


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


class Gemini:
    def __init__(self) -> None:
        cfg = settings()
        from google import genai

        if cfg.gemini_mode == "api_key":
            key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise LLMUnavailable("GEMINI_MODE=api_key but no GEMINI_API_KEY set")
            self.client = genai.Client(api_key=key)
        else:
            self.client = genai.Client(vertexai=True, project=cfg.gcp_project, location=cfg.gemini_location)
        self.mode = cfg.gemini_mode
        self._sem = asyncio.Semaphore(int(os.environ.get("GEMINI_CONCURRENCY", "8")))

    async def json(
        self,
        model: str,
        system: str,
        parts: list[dict[str, Any]],
        schema: dict[str, Any],
        thinking_level: str = "low",
        retries: int = 2,
    ) -> LLMResult:
        _check_model(model)
        body: dict[str, Any] = {
            "model": model,
            "system_instruction": system,
            "input": parts,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
            "generation_config": {"thinking_level": thinking_level},
            "store": False,
        }
        last: Exception | None = None
        for attempt in range(retries + 1):
            t0 = time.perf_counter()
            try:
                async with self._sem:
                    it = await self.client.aio.interactions.create(**body)
                text = it.output_text or ""
                if not text and it.steps:
                    text = "".join(getattr(getattr(s, "content", None), "text", "") or "" for s in it.steps)
                data = json.loads(text)
                u = it.usage
                return LLMResult(
                    data=data,
                    model=model,
                    tokens_in=getattr(u, "total_input_tokens", None) if u else None,
                    tokens_out=((getattr(u, "total_output_tokens", 0) or 0) + (getattr(u, "total_thought_tokens", 0) or 0)) if u else None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    raw_text=text,
                )
            except json.JSONDecodeError as exc:
                last = exc
            except Exception as exc:  # network / quota: back off and retry
                last = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Gemini call failed after {retries + 1} attempts: {last}")

    async def transcribe(self, model: str, audio: dict[str, Any], transcription_config: dict[str, Any]) -> LLMResult:
        """Speech-to-text model (no thinking, no system instruction)."""
        _check_model(model)
        t0 = time.perf_counter()
        async with self._sem:
            it: Any = await self.client.aio.interactions.create(
                model=model, input=[audio], generation_config={"transcription_config": transcription_config}, store=False
            )
        u = it.usage
        return LLMResult(
            data=it.output_text or "",
            model=model,
            tokens_in=getattr(u, "total_input_tokens", None) if u else None,
            tokens_out=getattr(u, "total_output_tokens", None) if u else None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            raw_text=it.output_text or "",
        )

    async def text(
        self, model: str, system: str, parts: list[dict[str, Any]], thinking_level: str = "low", tools: list[dict[str, Any]] | None = None
    ) -> LLMResult:
        _check_model(model)
        body: dict[str, Any] = {
            "model": model,
            "system_instruction": system,
            "input": parts,
            "generation_config": {"thinking_level": thinking_level},
            "store": False,
        }
        if tools:
            body["tools"] = tools
        t0 = time.perf_counter()
        async with self._sem:
            it = await self.client.aio.interactions.create(**body)
        u = it.usage
        return LLMResult(
            data=it.output_text or "",
            model=model,
            tokens_in=getattr(u, "total_input_tokens", None) if u else None,
            tokens_out=getattr(u, "total_output_tokens", None) if u else None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            raw_text=it.output_text or "",
        )


_client: Gemini | None = None


def gemini() -> Gemini:
    global _client
    if _client is None:
        if not settings().gemini_configured:
            raise LLMUnavailable("Gemini credentials are not configured (no ADC / service account / API key)")
        _client = Gemini()
    return _client


def set_gemini(client: Any) -> None:
    """Tests inject a fake client with the same async ``json``/``text`` interface."""
    global _client
    _client = client

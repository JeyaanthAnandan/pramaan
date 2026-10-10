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
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings

log = logging.getLogger("pramaan.llm")

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

    # Interactions API first; if this project's endpoint does not serve it (404 / unimplemented),
    # fall back once to models.generate_content with the same schema, thinking level and media
    # resolution, and remember the choice for the rest of the process.
    use_interactions: bool = True

    @staticmethod
    def _unavailable(exc: Exception) -> bool:
        msg = str(exc)
        return any(
            k in msg for k in ("404", "NOT_FOUND", "Not Found", "not found", "UNIMPLEMENTED", "501", "not supported", "Unknown name")
        )

    async def _call(
        self,
        model: str,
        system: str | None,
        parts: list[dict[str, Any]],
        schema: dict[str, Any] | None = None,
        thinking_level: str | None = "low",
        transcription_config: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, int | None, int | None]:
        if self.use_interactions:
            body: dict[str, Any] = {"model": model, "input": parts, "store": False}
            if system:
                body["system_instruction"] = system
            if schema is not None:
                body["response_format"] = {"type": "text", "mime_type": "application/json", "schema": schema}
            gen: dict[str, Any] = {}
            if thinking_level:
                gen["thinking_level"] = thinking_level
            if transcription_config:
                gen["transcription_config"] = transcription_config
            if gen:
                body["generation_config"] = gen
            if tools:
                body["tools"] = tools
            try:
                async with self._sem:
                    it: Any = await self.client.aio.interactions.create(**body)
                text = it.output_text or ""
                if not text and getattr(it, "steps", None):
                    text = "".join(getattr(getattr(st, "content", None), "text", "") or "" for st in it.steps)
                u = it.usage
                tin = getattr(u, "total_input_tokens", None) if u else None
                tout = ((getattr(u, "total_output_tokens", 0) or 0) + (getattr(u, "total_thought_tokens", 0) or 0)) if u else None
                return text, tin, tout
            except Exception as exc:
                if not self._unavailable(exc):
                    raise
                log.warning("Interactions API unavailable (%s); falling back to models.generate_content", str(exc)[:160])
                self.use_interactions = False
        return await self._generate(model, system, parts, schema, thinking_level, transcription_config)

    async def _generate(
        self,
        model: str,
        system: str | None,
        parts: list[dict[str, Any]],
        schema: dict[str, Any] | None,
        thinking_level: str | None,
        transcription_config: dict[str, Any] | None,
    ) -> tuple[str, int | None, int | None]:
        from google.genai import types

        if transcription_config:  # speech-only model: use Flash audio understanding instead
            model, system, thinking_level = (
                settings().model_flash,
                "Transcribe the audio verbatim in its original script. Output only the transcript.",
                "low",
            )
            parts = [{"type": "text", "text": "Transcribe this voice note."}, *parts]
        gparts: list[Any] = []
        hi_res = False
        for prt in parts:
            if prt["type"] == "text":
                gparts.append(types.Part(text=prt["text"]))
            else:
                gparts.append(types.Part.from_bytes(data=base64.b64decode(prt["data"]), mime_type=prt["mime_type"]))
                hi_res |= prt.get("resolution") == "high"
        cfg: dict[str, Any] = {}
        if system:
            cfg["system_instruction"] = system
        if schema is not None:
            cfg["response_mime_type"] = "application/json"
            cfg["response_json_schema"] = schema
        if thinking_level:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_level=types.ThinkingLevel(thinking_level.upper()))
        if hi_res:
            cfg["media_resolution"] = "MEDIA_RESOLUTION_HIGH"
        async with self._sem:
            r: Any = await self.client.aio.models.generate_content(
                model=model, contents=types.Content(role="user", parts=gparts), config=types.GenerateContentConfig(**cfg)
            )
        um = getattr(r, "usage_metadata", None)
        return (
            (r.text or ""),
            getattr(um, "prompt_token_count", None),
            (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0),
        )

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
        last: Exception | None = None
        for attempt in range(retries + 1):
            t0 = time.perf_counter()
            try:
                text, tin, tout = await self._call(model, system, parts, schema, thinking_level)
                return LLMResult(json.loads(text), model, tin, tout, int((time.perf_counter() - t0) * 1000), text)
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
        text, tin, tout = await self._call(model, None, [audio], None, None, transcription_config)
        return LLMResult(
            text, model if self.use_interactions else settings().model_flash, tin, tout, int((time.perf_counter() - t0) * 1000), text
        )

    async def text(
        self, model: str, system: str, parts: list[dict[str, Any]], thinking_level: str = "low", tools: list[dict[str, Any]] | None = None
    ) -> LLMResult:
        _check_model(model)
        t0 = time.perf_counter()
        text, tin, tout = await self._call(model, system, parts, None, thinking_level, tools=tools)
        return LLMResult(text, model, tin, tout, int((time.perf_counter() - t0) * 1000), text)


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

"""Try one photo: watch two Gemini models read a single document, live, in seconds.

For a judge with two minutes, or an exporter deciding whether to trust Pramaan with a year of bills:
upload one photo (or pick a bundled sample) and the same agents a full run uses read it in front of
you. Gemini 3.8 Flash classifies the page and reads every value with its box; Gemini 3.5 Flash-Lite
re-reads each cropped box blind; the same comparison decides agree / check. Each step is streamed as
it lands (server-sent events over a POST), so boxes appear on the photo and turn green one by one.

Nothing is stored: the photo is read in memory and dropped with the request. Without Gemini (or with
live runs switched off) the bundled samples replay their recorded ground truth, labelled as a replay,
and uploads are refused with a clear message.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.agents import replay
from app.agents.normalize import canonical_text, normalize_fields
from app.agents.readers import parse_fields
from app.agents.schemas import FIELDS
from app.agents.second_reader import compare, crop
from app.config import settings
from app.evidence.models import ExtractedField, Project

router = APIRouter(prefix="/api")

# bundled sample photos a visitor can try without a document of their own (demo/out/<name>.jpg)
SAMPLES = {
    "gas-2026-03": "Gas invoice, March 2026",
    "scrap-2026-06-to-09": "Handwritten scrap log (Hindi, Punjabi)",
    "rod-ISR-2026-038": "Stainless wire rod invoice",
}
MAX_CHECKS = 40  # blind second reads per photo: bounds the cost of one try
REPLAY_PACE = 0.5  # seconds per step when replaying, so the steps can be followed


def live() -> bool:
    cfg = settings()
    return cfg.gemini_configured and cfg.live_runs_enabled


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _label(doc_type: str, f: ExtractedField) -> str:
    return f.label or FIELDS.get(doc_type, {}).get(f.field_key, (f.field_key,))[0]


async def read_one(
    image: bytes, filename: str, use_live: bool, project: Project, display: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    """The three reading steps on one JPEG, as events: start, classified, extracted, checked (one per
    value, in the order the second reads finish) and done; error if a model call fails."""
    from app.agents.readers import classify, extract, second_read

    cfg = settings()
    r1 = cfg.model_flash if use_live else replay.REPLAY_MODEL
    r2 = cfg.model_lite if use_live else replay.REPLAY_MODEL
    t_start = time.perf_counter()
    tokens = 0
    yield {"stage": "start", "live": use_live, "reader1": r1, "reader2": r2} | ({"image": display} if display else {})

    t = time.perf_counter()
    if use_live:
        res = await classify(image, "image/jpeg")
        cls = dict(res.data)
        tokens += (res.tokens_in or 0) + (res.tokens_out or 0)
    else:
        await asyncio.sleep(REPLAY_PACE)
        cls = replay.classify(filename) or {"doc_type": "other"}
    doc_type = str(cls.get("doc_type") or "other")
    yield {
        "stage": "classified",
        "doc_type": doc_type,
        "title": str(cls.get("title") or ""),
        "languages": list(cls.get("languages") or []),
        "confidence": float(cls.get("confidence") or 0),
        "ms": int((time.perf_counter() - t) * 1000),
        "model": r1,
    }
    if doc_type == "other" or doc_type not in FIELDS:
        yield {
            "stage": "done",
            "note": "not_cbam",
            "ms": int((time.perf_counter() - t_start) * 1000),
            "tokens": tokens,
            "agree": 0,
            "review": 0,
        }
        return

    t = time.perf_counter()
    if use_live:
        res = await extract(image, "image/jpeg", doc_type, project)
        fields = parse_fields(res.data, "try")
        tokens += (res.tokens_in or 0) + (res.tokens_out or 0)
    else:
        await asyncio.sleep(REPLAY_PACE)
        fields = parse_fields({"fields": replay.extract(filename) or []}, "try")
    normalize_fields(fields, doc_type, project)
    items = [
        {
            "id": f"v{i}",
            "field_key": f.field_key,
            "label": _label(doc_type, f),
            "value_text": f.value_text,
            "value_num": f.value_num,
            "unit": f.unit,
            "box_2d": f.box_2d,
            "period": f.period,
        }
        for i, f in enumerate(fields)
    ]
    checkable = [(f"v{i}", f) for i, f in enumerate(fields) if f.box_2d][:MAX_CHECKS]
    yield {
        "stage": "extracted",
        "fields": items,
        "checking": [i for i, _ in checkable],
        "ms": int((time.perf_counter() - t) * 1000),
        "model": r1,
    }

    t = time.perf_counter()
    gate = asyncio.Semaphore(12)

    async def check(fid: str, f: ExtractedField) -> dict[str, Any]:
        async with gate:
            try:
                crop_bytes, padded = crop(image, f.box_2d or [0, 0, 1000, 1000])
                used = 0
                if use_live:
                    rr = await second_read(crop_bytes, f.field_key, f.unit)
                    reading = dict(rr.data)
                    reading["value_text"] = canonical_text(f.field_key, str(reading.get("value_text") or ""))
                    used = (rr.tokens_in or 0) + (rr.tokens_out or 0)
                else:
                    await asyncio.sleep(0.04)
                    reading = replay.second_read(filename, f.model_dump()) or {"value_text": "", "legible": False}
                sr = compare(f.value_text, f.value_num, f.unit, reading, r2, padded)
                ok = sr.agrees and not sr.corrected_from
                return {
                    "stage": "checked",
                    "id": fid,
                    "reading": sr.reading_value,
                    "agrees": ok,
                    "reason": sr.reason,
                    "corrected_from": sr.corrected_from,
                    "crop_box": padded,  # exactly what the second reader saw
                    "tokens": used,
                }
            except Exception as exc:  # one failed crop is a value to check, not a failed try
                return {
                    "stage": "checked",
                    "id": fid,
                    "reading": "",
                    "agrees": False,
                    "reason": f"second reader failed ({exc.__class__.__name__})",
                    "corrected_from": None,
                    "tokens": 0,
                }

    agree = review = 0
    # the second reads run as tasks: if the visitor leaves (the stream is cancelled or closed), the reads
    # nobody will see are cancelled too instead of finishing their paid calls
    tasks = [asyncio.ensure_future(check(i, f)) for i, f in checkable]
    try:
        for fut in asyncio.as_completed(tasks):
            ev = await fut
            tokens += ev.pop("tokens")
            agree, review = (agree + 1, review) if ev["agrees"] else (agree, review + 1)
            yield ev
    finally:
        for task in tasks:
            task.cancel()
    yield {
        "stage": "done",
        "ms": int((time.perf_counter() - t_start) * 1000),
        "second_ms": int((time.perf_counter() - t) * 1000),
        "tokens": tokens,
        "agree": agree,
        "review": review,
        "unchecked": len(items) - len(checkable),
    }


async def _stream(image: bytes, filename: str, use_live: bool, project: Project, display: str | None) -> AsyncIterator[str]:
    try:
        async for ev in read_one(image, filename, use_live, project, display):
            yield _sse(ev)
    except TimeoutError:
        yield _sse({"stage": "error", "message": "Gemini took too long to answer; please try again."})
    except Exception as exc:
        yield _sse({"stage": "error", "message": f"The reading stopped ({exc.__class__.__name__}); please try again."})


def _respond(image: bytes, filename: str, use_live: bool, project: Project, display: str | None = None) -> StreamingResponse:
    return StreamingResponse(
        _stream(image, filename, use_live, project, display),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/try")
def try_status() -> dict[str, Any]:
    cfg = settings()
    return {
        "live": live(),
        "reader1": cfg.model_flash,
        "reader2": cfg.model_lite,
        "samples": [{"name": k, "title": v} for k, v in SAMPLES.items()],
        "max_checks": MAX_CHECKS,
    }


@router.get("/try/sample/{name}/image")
def try_sample_image(name: str) -> Response:
    if name not in SAMPLES:
        raise HTTPException(404, "unknown sample")
    path = settings().demo_dir / "out" / f"{name}.jpg"
    return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.post("/try/sample/{name}")
def try_sample(request: Request, name: str) -> StreamingResponse:
    """Read one bundled sample photo: live when Gemini is configured, else its recorded replay."""
    from app.api.routes import _ai_limit
    from app.demo.loader import demo_project

    if name not in SAMPLES:
        raise HTTPException(404, "unknown sample")
    use_live = live()
    if use_live:
        _ai_limit(request, "try")
    path = settings().demo_dir / "out" / f"{name}.jpg"
    return _respond(path.read_bytes(), path.name, use_live, demo_project())


@router.post("/try")
async def try_upload(request: Request, file: UploadFile = File(...)) -> StreamingResponse:  # noqa: B008
    """Read one photo of the visitor's own: needs live Gemini; the photo is never stored."""
    from app.api.routes import ALLOWED, MAX_UPLOAD, _ai_limit
    from app.evidence.normalize import to_pages

    if not live():
        raise HTTPException(
            503, "Reading your own photo needs live Gemini, which is not switched on for this server. The samples work without it."
        )
    _ai_limit(request, "try")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "larger than 15 MB")
    ctype = (file.content_type or "").lower()
    name = file.filename or "photo"
    if ctype in {"", "application/octet-stream"} and name.lower().endswith((".heic", ".heif")):
        ctype = "image/heic"
    if ctype not in ALLOWED:
        raise HTTPException(415, f"unsupported type {ctype or 'unknown'}: use a photo (JPEG, PNG, HEIC) or a PDF")
    try:
        jpeg = to_pages(data, ctype, max_pages=1)[0][0]  # a PDF: only its first page is rendered
    except Exception as exc:
        raise HTTPException(422, f"could not read the file ({exc.__class__.__name__})") from exc
    # no product lines: values are read as printed, not assigned to a line
    return _respond(jpeg, "upload.jpg", True, Project(name="Try one photo", company=""), _display(jpeg))


def _display(jpeg: bytes) -> str:
    """A small copy of the page as read (orientation applied; a PDF's first page), so the boxes land on
    what the readers saw even where the browser cannot show the upload itself (HEIC, PDF)."""
    from PIL import Image

    img = Image.open(io.BytesIO(jpeg))
    img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()

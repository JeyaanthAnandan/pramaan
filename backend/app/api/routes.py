"""REST + SSE API (brief 7.5). All JSON under /api; the SPA is served at /."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app import access, refdata
from app.agents.workflow import BUS, RUNS, execute, recalculate
from app.cbam.golden import run_all
from app.config import settings
from app.demo import loader
from app.evidence import blobs
from app.evidence.models import DOC_TYPES, Document, Evidence, ProcessDef, Project, Run, ShareLink, now
from app.evidence.store import store

router = APIRouter(prefix="/api", dependencies=[Depends(access.require)])
_run_log: dict[str, deque[float]] = defaultdict(deque)
MAX_UPLOAD = 15 * 1024 * 1024
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}


def _project(pid: str) -> Project:
    p = store().get_project(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return p


def _public(p: Project) -> dict[str, Any]:
    """Project as the API shows it: never the passcode hash."""
    return {**p.model_dump(exclude={"access_hash"}), "protected": bool(p.access_hash)}


def _result(pid: str) -> dict[str, Any]:
    r = store().get_latest_result(pid)
    if r is None:
        raise HTTPException(404, "no results yet - run the agents first")
    if "operations" not in r:  # saved by an older engine version: recompute from the same evidence
        r = recalculate(pid)
    return r


# ------------------------------------------------------------------ projects & documents


class NewProject(BaseModel):
    name: str
    company: str
    country: str = "India"
    city: str = ""
    months_to: int | None = None  # last month of the reporting period (1-12); default Jan-Sep YTD
    processes: list[ProcessDef] | None = None  # scripted set-ups; people use PUT /product-lines


@router.post("/projects")
def create_project(body: NewProject, request: Request, response: Response) -> dict[str, Any]:
    """An exporter's own project: private (passcode), product lines set by the owner or proposed by
    the ProductLines agent from the uploaded invoices."""
    from app.cbam.products import countries, months_upto, sync_supplier_requests

    if body.country not in countries():
        raise HTTPException(422, "unknown country (use the name in the EU default-value tables)")
    p = Project(
        name=body.name[:120],
        company=body.company[:160],
        country=body.country,
        city=body.city[:120],
        processes=body.processes or [],
        processes_confirmed=bool(body.processes),
    )
    if body.months_to:
        p.months, p.period_label = months_upto(p.year, body.months_to)
    sync_supplier_requests(p)
    code = access.new_passcode()
    p.access_hash = access.hash_code(p.id, code)
    store().put_project(p)
    access.set_cookie(request, response, p.id, code)
    return {**_public(p), "access_key": code}


class Unlock(BaseModel):
    passcode: str


_unlock_log: dict[str, deque[float]] = defaultdict(deque)


@router.post("/projects/{pid}/unlock")
def unlock(pid: str, body: Unlock, request: Request, response: Response) -> dict[str, Any]:
    ip = _client_ip(request)
    window, t = _unlock_log[ip], time.time()
    while window and t - window[0] > 3600:
        window.popleft()
    if len(window) >= 20:
        raise HTTPException(429, "too many passcode attempts; try again later")
    window.append(t)
    p = _project(pid)
    if p.access_hash and not access.matches(pid, p.access_hash, body.passcode):
        raise HTTPException(401, "wrong passcode")
    if p.access_hash:
        access.set_cookie(request, response, pid, body.passcode)
    return {"ok": True, "project_id": pid}


STALE_RUN_S = 30 * 60  # a run still "running" after this was cut off (instance restarted); live runs take minutes


def runs_settled(pid: str) -> list[Run]:
    """The project's runs, with any run cut off by a server restart marked as interrupted, so it never
    blocks the project ("a run is already in progress") or spins in the UI forever."""
    import datetime as dt

    runs = store().list_runs(pid)
    t = dt.datetime.now(dt.UTC)
    for r in runs:
        if r.status != "running" or r.id in RUNS:  # RUNS: executing on this instance right now
            continue
        try:
            age = (t - dt.datetime.fromisoformat(r.started_at)).total_seconds()
        except (ValueError, TypeError):
            continue
        if age > STALE_RUN_S:
            r.status, r.finished_at = "error", now()
            r.error = "interrupted: the server restarted during this run; run it again"
            store().put_run(r)
    return runs


@router.get("/projects/{pid}")
def get_project(pid: str) -> dict[str, Any]:
    p = _project(pid)
    st = store()
    runs = runs_settled(pid)
    last = runs[-1] if runs else None
    return {
        "project": _public(p),
        "documents": [d.model_dump() for d in sorted(st.list_documents(pid), key=lambda d: (d.doc_type or "zz", d.filename))],
        "last_run": last.model_dump(exclude={"events"}) if last else None,
        "running": any(r.status == "running" for r in runs),
        "has_result": st.get_latest_result(pid) is not None,
    }


class ProjectPatch(BaseModel):
    fx_inr_per_eur: str | None = None
    projection_price_eur: str | None = None
    supplier_status: dict[str, str] | None = None  # process_id -> status
    name: str | None = None
    company: str | None = None
    city: str | None = None
    country: str | None = None
    months_to: int | None = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch) -> dict[str, Any]:
    from app.cbam.products import countries, months_upto

    p = _project(pid)
    if not p.is_demo:  # the fictional sample's identity and period are fixed
        for name, limit in (("name", 120), ("company", 160), ("city", 120)):
            v = getattr(body, name)
            if v is not None and v.strip():
                setattr(p, name, v.strip()[:limit])
        if body.country is not None:
            if body.country not in countries():
                raise HTTPException(422, "unknown country (use the name in the EU default-value tables)")
            p.country = body.country
        if body.months_to is not None:
            p.months, p.period_label = months_upto(p.year, body.months_to)
    for name in ("fx_inr_per_eur", "projection_price_eur"):
        v = getattr(body, name)
        if v is not None:
            if v == "":
                setattr(p, name, None)
            else:
                try:
                    d = Decimal(v)
                except InvalidOperation as exc:
                    raise HTTPException(422, f"{name} must be a number") from exc
                if d <= 0 or d > 100000:
                    raise HTTPException(422, f"{name} out of range")
                setattr(p, name, str(d))
    if body.supplier_status:
        for sr in p.supplier_requests:
            if sr.process_id in body.supplier_status:
                st = body.supplier_status[sr.process_id]
                if st not in {"not_requested", "requested", "received", "verified"}:
                    raise HTTPException(422, "bad supplier status")
                sr.status = st  # type: ignore[assignment]
                sr.updated_at = now()
    store().put_project(p)
    if store().get_latest_result(pid):
        recalculate(pid)
    return _public(p)


@router.post("/projects/{pid}/documents")
async def upload(pid: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:  # noqa: B008
    """Photos (JPG/PNG/WebP/HEIC) and PDFs. Everything is normalised to JPEG pages (one document per
    page) so cropping, the blind second reader and the Evidence Lens work the same for every input."""
    _project(pid)
    return {"documents": [d.model_dump() for d in await save_uploads(pid, files)]}


async def save_uploads(pid: str, files: list[UploadFile], uploaded_by: str = "owner", limit: int = 40) -> list[Document]:
    from app.evidence.normalize import to_pages

    out: list[Document] = []
    for f in files[:limit]:
        data = await f.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"{f.filename}: larger than 15 MB")
        ctype = (f.content_type or "").lower()
        name = f.filename or "upload"
        if ctype in {"", "application/octet-stream"} and name.lower().endswith((".heic", ".heif")):
            ctype = "image/heic"
        if ctype not in ALLOWED:
            raise HTTPException(415, f"{name}: unsupported type {ctype}")
        try:
            pages = to_pages(data, ctype)
        except Exception as exc:
            raise HTTPException(422, f"{name}: could not read the file ({exc.__class__.__name__})") from exc
        stem = name.rsplit(".", 1)[0]
        for i, (jpeg, w, h) in enumerate(pages):
            fname = f"{stem}.jpg" if len(pages) == 1 else f"{stem}-p{i + 1}.jpg"
            d = Document(
                project_id=pid,
                filename=fname,
                content_type="image/jpeg",
                uri="pending",
                width=w,
                height=h,
                title=fname,
                uploaded_by=uploaded_by,
            )
            d.uri, d.sha256 = blobs.save(pid, d.id, fname, jpeg, "image/jpeg")
            store().put_document(d)
            out.append(d)
    return out


@router.get("/projects/{pid}/documents/{doc_id}/image")
def document_image(pid: str, doc_id: str) -> Response:
    d = store().get_document(pid, doc_id)
    if d is None:
        raise HTTPException(404, "document not found")
    p = store().get_project(pid)
    cache = "public, max-age=3600" if p is not None and not p.access_hash else "private, max-age=3600"
    return Response(blobs.load(d.uri), media_type=d.content_type, headers={"Cache-Control": cache})


# ------------------------------------------------------------------ runs + SSE


class RunRequest(BaseModel):
    lang: str = "en"
    mode: str | None = None  # "live" | "replay" | None (auto)


@router.post("/projects/{pid}/runs")
async def start_run(pid: str, request: Request, body: RunRequest, background: BackgroundTasks) -> dict[str, Any]:
    p = _project(pid)
    cfg = settings()
    window = _run_log[pid]
    t = time.time()
    while window and t - window[0] > 3600:
        window.popleft()
    if len(window) >= cfg.max_runs_per_hour:
        raise HTTPException(429, "run limit reached for this project; try again later")
    if any(r.status == "running" for r in runs_settled(pid)):
        raise HTTPException(409, "a run is already in progress")
    mode = body.mode or ("live" if (cfg.gemini_configured and cfg.live_runs_enabled) else "replay")
    if mode == "live" and not cfg.gemini_configured:
        raise HTTPException(503, "Gemini is not configured on this server; use replay mode")
    if mode == "live":  # every visitor has a private sample copy: cap live (paid) runs per address too
        _ai_limit(request, "run")
    if p.is_demo:
        for d in store().list_documents(pid):  # re-run every agent on the sample docs
            if d.content_type.startswith("audio/"):
                continue  # voice notes are evidence already; they are not re-read as images
            d.state = "uploaded"
            d.doc_type = None
            store().put_document(d)
    window.append(t)
    run = Run(project_id=pid, mode=mode)  # type: ignore[arg-type]
    store().put_run(run)
    background.add_task(execute, run, p, mode, body.lang, 0.35)
    return {"run_id": run.id, "mode": mode}


@router.get("/projects/{pid}/runs")
def list_runs(pid: str) -> list[dict[str, Any]]:
    return [r.model_dump(exclude={"events"}) for r in store().list_runs(pid)]


@router.get("/projects/{pid}/runs/{run_id}")
def get_run(pid: str, run_id: str) -> dict[str, Any]:
    r = store().get_run(pid, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return r.model_dump()


@router.get("/projects/{pid}/runs/{run_id}/events")
async def run_events(pid: str, run_id: str, request: Request) -> StreamingResponse:
    async def gen():  # type: ignore[no-untyped-def]
        r = store().get_run(pid, run_id)
        live = RUNS.get(run_id)
        q = BUS.subscribe(run_id)
        try:
            sent = 0
            history = live.run.events if live else (r.events if r else [])
            for ev in list(history):
                sent = max(sent, ev.seq)
                yield f"event: timeline\ndata: {ev.model_dump_json()}\n\n"
            if not live:
                # The run may be executing on another Cloud Run instance: follow it through the store.
                while True:
                    cur = store().get_run(pid, run_id)
                    if cur is None:
                        break
                    for ev in cur.events:
                        if ev.seq > sent:
                            sent = ev.seq
                            yield f"event: timeline\ndata: {ev.model_dump_json()}\n\n"
                    if cur.status != "running" or await request.is_disconnected():
                        break
                    await asyncio.sleep(1.0)
                final = store().get_run(pid, run_id)
                yield f"event: end\ndata: {json.dumps({'status': final.status if final else 'unknown'})}\n\n"
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)  # type: ignore[arg-type]
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if ev is None:
                    final = store().get_run(pid, run_id)
                    yield f"event: end\ndata: {json.dumps({'status': final.status if final else 'unknown', 'metrics': final.metrics if final else {}})}\n\n"
                    return
                if ev.seq <= sent:
                    continue
                sent = ev.seq
                yield f"event: timeline\ndata: {ev.model_dump_json()}\n\n"
        finally:
            BUS.unsubscribe(run_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ evidence & results


@router.get("/projects/{pid}/evidence")
def list_evidence(pid: str) -> list[dict[str, Any]]:
    _project(pid)
    return [e.model_dump() for e in store().list_evidence(pid)]


class EvidencePatch(BaseModel):
    action: str  # approve | edit
    value_text: str | None = None
    value_num: str | None = None
    user: str = "owner"
    notes: str | None = None


@router.patch("/projects/{pid}/evidence/{eid}")
def patch_evidence(pid: str, eid: str, body: EvidencePatch) -> dict[str, Any]:
    st = store()
    x = st.get_evidence(pid, eid)
    if x is None:
        raise HTTPException(404, "evidence not found")
    before = {"value_text": x.value_text, "value_num": x.value_num, "status": x.status}
    if body.action == "edit":
        if body.value_text is None:
            raise HTTPException(422, "value_text required for edit")
        x.value_text = body.value_text
        if body.value_num is not None:
            try:
                Decimal(body.value_num)
            except InvalidOperation as exc:
                raise HTTPException(422, "value_num must be a number") from exc
            x.value_num = body.value_num
    elif body.action != "approve":
        raise HTTPException(422, "action must be approve or edit")
    x.status = "APPROVED"
    x.approved_by = (body.user or "owner")[:60]
    x.approved_at = now()
    x.notes = body.notes
    x.history.append({"at": x.approved_at, "by": x.approved_by, "action": body.action, "before": before})
    st.put_evidence([x])
    result = recalculate(pid)
    return {"evidence": x.model_dump(), "readiness": result["readiness"]}


@router.get("/projects/{pid}/results")
def results(pid: str) -> dict[str, Any]:
    _project(pid)
    return _result(pid)


# ------------------------------------------------------------------ exports & share


@router.get("/projects/{pid}/export/{kind}")
def export(pid: str, kind: str, lang: str = "en") -> Response:
    p = _project(pid)
    r = _result(pid)
    st = store()
    from app.exports import pack, pdf, xlsx

    stamp = r["computed_at"][:10]
    if kind == "pdf":
        return Response(
            pdf.render(p, r, lang),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="pramaan-cbam-report-{stamp}.pdf"'},
        )
    if kind == "xlsx":
        return Response(
            xlsx.render(p, r, st.list_evidence(pid), st.list_documents(pid)),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="pramaan-cbam-workbook-{stamp}.xlsx"'},
        )
    if kind == "pack":
        return Response(
            pack.render(p, r, st.list_evidence(pid), st.list_documents(pid), st.list_runs(pid)),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="pramaan-verifier-pack-{stamp}.zip"'},
        )
    raise HTTPException(404, "unknown export")


@router.post("/projects/{pid}/share")
def share(pid: str) -> dict[str, Any]:
    p = _project(pid)
    r = _result(pid)
    s = ShareLink(project_id=p.id, summary_snapshot=r["buyer_summary"])
    store().put_share(s)
    base = settings().public_base_url
    return {"token": s.token, "url": f"{base}/share/{s.token}" if base else f"/share/{s.token}"}


@router.get("/share/{token}")
def get_share(token: str) -> dict[str, Any]:
    s = store().get_share(token)
    if s is None or s.kind != "buyer":
        raise HTTPException(404, "link not found or expired")
    return {"summary": s.summary_snapshot, "created_at": s.created_at}


# ------------------------------------------------------------------ product lines (own projects)


class LineIn(BaseModel):
    id: str | None = None
    name: str = ""
    cn: str = ""
    precursor_name: str = ""
    precursor_cn: str = ""
    precursor_supplier: str = ""
    source: str | None = None
    doc_ids: list[str] | None = None
    rationale: str | None = None


class LinesIn(BaseModel):
    lines: list[LineIn]
    confirm: bool = True


@router.put("/projects/{pid}/product-lines")
def put_product_lines(pid: str, body: LinesIn) -> dict[str, Any]:
    """Set or confirm the product lines (each CN code is validated against the official refdata)."""
    from app.cbam.products import build_line, sync_supplier_requests

    p = _project(pid)
    if p.is_demo:
        raise HTTPException(409, "the sample factory's product lines are fixed")
    if not 1 <= len(body.lines) <= 6:
        raise HTTPException(422, "between 1 and 6 product lines")
    lines, problems = [], {}
    for i, raw in enumerate(body.lines):
        src = raw.source if raw.source in {"owner", "ai"} else "owner"
        pdef, errors = build_line(raw.model_dump(), f"P{i + 1}", p.country, source=src)
        if pdef is None:
            problems[str(i)] = errors
        else:
            lines.append(pdef)
    if problems:
        raise HTTPException(422, {"message": "Some product lines are not usable", "lines": problems})
    cns = [x.cn for x in lines]
    if len(set(cns)) != len(cns):
        raise HTTPException(422, {"message": "Each product line needs its own CN code", "lines": {}})
    p.processes = lines
    p.processes_confirmed = body.confirm
    sync_supplier_requests(p)
    store().put_project(p)
    if store().get_latest_result(pid):
        recalculate(pid)
    return _public(p)


@router.post("/projects/{pid}/product-lines/suggest")
async def suggest_product_lines(request: Request, pid: str) -> dict[str, Any]:
    """ProductLines agent on demand: Gemini proposes lines from the uploaded export and steel-input
    invoices (classifying them first if needed). Nothing is saved until the owner confirms."""
    from app.agents.product_lines import propose
    from app.agents.readers import classify

    p = _project(pid)
    _ai_limit(request, "suggest")
    if not settings().gemini_configured:
        raise HTTPException(503, "Proposing product lines needs live Gemini, which is not configured on this server.")
    docs = [d for d in store().list_documents(pid) if d.content_type.startswith("image/")]
    for d in docs:
        if not d.doc_type:
            r = await classify(blobs.load(d.uri), d.content_type)
            d.doc_type = r.data.get("doc_type")
            d.languages = r.data.get("languages") or []
            d.title = r.data.get("title") or d.filename
            d.doc_type_confidence = float(r.data.get("confidence") or 0)
            d.state = "classified"
            store().put_document(d)
    out = await propose(p, docs)
    return {**out, "lines": [x.model_dump() for x in out["lines"]]}


@router.get("/refdata/cn/search")
def cn_search(q: str = "", country: str = "India") -> list[dict[str, Any]]:
    from app.cbam.products import search

    return search(q[:60], country)


@router.get("/refdata/cn/{cn}")
def cn_lookup(cn: str, country: str = "India", role: str = "good") -> dict[str, Any]:
    from app.cbam.products import cn_info

    return cn_info(cn[:20], country, "precursor" if role == "precursor" else "good")


@router.get("/refdata/countries")
def cn_countries() -> list[str]:
    from app.cbam.products import countries

    return countries()


# ------------------------------------------------------------------ decarbonisation what-if (X2)


class WhatIf(BaseModel):
    process_id: str
    rod_see: str | None = None
    rod_sefa: str | None = None
    heating: str = "gas"
    scrap_pct: str | None = None  # scrap and cut-offs as % of rod consumed
    gas_gj_per_t: str | None = None  # heat-treatment gas per tonne (NCV)


@router.post("/projects/{pid}/whatif")
def whatif(pid: str, body: WhatIf) -> dict[str, Any]:
    from app.cbam.whatif import simulate

    _project(pid)
    r = _result(pid)

    def num(v: str | None, name: str, hi: int = 50) -> Decimal | None:
        if v in (None, ""):
            return None
        try:
            d = Decimal(str(v))
        except InvalidOperation as exc:
            raise HTTPException(422, f"{name} must be a number") from exc
        if not d.is_finite() or d < 0 or d > hi:
            raise HTTPException(422, f"{name} out of range")
        return d

    if body.heating not in {"gas", "electric"}:
        raise HTTPException(422, "heating must be gas or electric")
    try:
        return simulate(
            r,
            body.process_id,
            num(body.rod_see, "rod_see"),
            num(body.rod_sefa, "rod_sefa"),
            body.heating,
            scrap_pct=num(body.scrap_pct, "scrap_pct", 60),
            gas_gj_per_t=num(body.gas_gj_per_t, "gas_gj_per_t", 20),
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


# ------------------------------------------------------------------ voice notes (X1)

AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/m4a", "audio/mpeg", "audio/wav", "audio/aac"}
VOICE_FIELDS = {"scrap_t", "produced_t", "rod_consumed_t"}


@router.post("/projects/{pid}/voice")
async def voice_note(
    request: Request,
    pid: str,
    audio: UploadFile = File(...),  # noqa: B008
    field_key: str = Form(...),
    process: str = Form(...),
    period: str = Form(...),
    lang: str = Form("hi"),
) -> dict[str, Any]:
    """A supervisor answers a gap question by voice (Hindi, Punjabi, Tamil, English)."""
    from app.agents.voice import read_value, transcribe

    p = _project(pid)
    _ai_limit(request, "voice")
    if not settings().gemini_configured:
        raise HTTPException(503, "Voice notes need live Gemini (gemini-3.5-transcribe), which is not configured on this server.")
    if field_key not in VOICE_FIELDS or process not in {x.id for x in p.processes} or period not in p.months:
        raise HTTPException(422, "unknown field, process or month")
    data = await audio.read()
    if not data or len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "voice note must be under 5 MB (about 30 s)")
    mime = (audio.content_type or "audio/webm").split(";")[0].lower()
    if mime not in AUDIO_TYPES:
        raise HTTPException(415, f"unsupported audio type {mime}")
    lang = lang if lang in {"hi", "pa", "ta", "en"} else "hi"
    proc = next(x for x in p.processes if x.id == process)
    d = Document(
        project_id=pid,
        filename=f"voice-{field_key}-{process}-{period}.{mime.split('/')[1]}",
        content_type=mime,
        uri="pending",
        doc_type="voice_note",
        languages=[lang],
        period=[period, period],
        state="extracted",
        title=f"Voice note · {proc.name} · {period}",
    )
    d.uri, d.sha256 = blobs.save(pid, d.id, d.filename, data, mime)
    store().put_document(d)
    t = await transcribe(data, mime, lang)
    transcript = str(t.data).strip()
    r = await read_value(transcript, field_key, period, lang)
    v = r.data if isinstance(r.data, dict) else {}
    num: str | None = None
    try:
        num = str(Decimal(str(v.get("value_num", "")).strip())) if v.get("found") else None
    except InvalidOperation:
        num = None
    if num is None:
        return {"document": d.model_dump(), "transcript": transcript, "evidence": None, "note": "No quantity found in the voice note."}
    unit = str(v.get("unit") or "t").strip().lower()
    if unit in {"kg", "kgs", "किलो", "ਕਿਲੋ", "கிலோ"}:
        num, unit = str(Decimal(num) / 1000), "t"
    else:
        unit = "t"
    ev = Evidence(
        project_id=pid,
        doc_id=d.id,
        field_key=field_key,
        label=f"Voice note · {proc.name}",
        value_text=str(v.get("value_text", "")) or num,
        value_num=num,
        unit=unit,
        box_2d=None,
        period=period,
        process=process,
        extractor_model=f"{t.model} + {r.model}",
        status="NEEDS_REVIEW",
        notes=f"Transcript ({lang}): {transcript}\nQuote: {v.get('quote', '')}",
    )
    store().put_evidence([ev])
    recalculate(pid)
    return {"document": d.model_dump(), "transcript": transcript, "evidence": ev.model_dump()}


# ------------------------------------------------------------------ letters, plan, copilot


class LetterRequest(BaseModel):
    process_id: str
    lang: str = "en"


class SupplierLinkIn(BaseModel):
    process_id: str


@router.post("/projects/{pid}/supplier-link")
def supplier_link(pid: str, body: SupplierLinkIn, request: Request) -> dict[str, Any]:
    """One upload link per product line for the steel-input supplier (no account needed)."""
    from app.api.supplier import ensure_link, public_url

    p = _project(pid)
    proc = next((x for x in p.processes if x.id == body.process_id), None)
    if proc is None:
        raise HTTPException(404, "process not found")
    link = ensure_link(p, proc)
    return {"token": link.token, "url": public_url(request, f"/supplier/{link.token}")}


@router.post("/projects/{pid}/supplier-letter")
def supplier_letter(pid: str, body: LetterRequest, request: Request) -> dict[str, Any]:
    from app.api.supplier import ensure_link, public_url
    from app.exports.letters import supplier_letter as make

    p = _project(pid)
    r = _result(pid)
    proc = next((x for x in p.processes if x.id == body.process_id), None)
    if proc is None:
        raise HTTPException(404, "process not found")
    link = ensure_link(p, proc)  # the letter carries the supplier's upload link
    url = public_url(request, f"/supplier/{link.token}")
    letter = make(p, proc, r, body.lang, link_url=url)
    for sr in p.supplier_requests:
        if sr.process_id == proc.id:
            sr.letter_lang = body.lang
    store().put_project(p)
    return {**letter, "link": {"token": link.token, "url": url}}


@router.get("/projects/{pid}/monitoring-plan")
def monitoring_plan(pid: str, lang: str = "en") -> dict[str, Any]:
    p = _project(pid)
    r = _result(pid)
    from app.exports.monitoring_plan import build

    return build(p, r, store().list_documents(pid), lang)


class Ask(BaseModel):
    question: str
    lang: str = "en"


_ai_log: dict[tuple[str, str], deque[float]] = defaultdict(deque)
# Gemini-backed endpoints are capped per address and hour (runs are capped per project), so a script
# cannot run up the demo's bill; the caps sit well above what a room of judges asks.
AI_CALLS_PER_HOUR = {"copilot": 120, "voice": 60, "suggest": 30, "supplier": 30, "run": 12}


def _ai_limit(request: Request, bucket: str) -> None:
    window, t = _ai_log[(bucket, _client_ip(request))], time.time()
    while window and t - window[0] > 3600:
        window.popleft()
    if len(window) >= AI_CALLS_PER_HOUR[bucket]:
        raise HTTPException(429, "too many requests from this address in the last hour; try again later")
    window.append(t)


@router.post("/copilot/ask")
async def copilot_ask(request: Request, body: Ask) -> dict[str, Any]:
    from app.copilot.service import answer

    _ai_limit(request, "copilot")
    q = body.question.strip()
    if not q or len(q) > 500:
        raise HTTPException(422, "question must be 1-500 characters")
    return await answer(q, body.lang)


@router.get("/projects/{pid}/explanations")
def explanations(pid: str, lang: str = "en") -> dict[str, Any]:
    """The deterministic explanations in the reader's language (numbers guarded, no model call)."""
    from app.agents.explainer import TEMPLATES, guard, template_sections

    secs = template_sections(_result(pid), lang if lang in TEMPLATES else "en")
    tree = _result(pid)["calc_tree"]
    for x in secs:
        ok, bad = guard(x["text"], tree, [c["page"] for c in x["citations"]])
        if not ok:  # a template bug must never ship a number that is not in the tree
            raise HTTPException(500, f"explanation template introduced numbers: {bad}")
    return {"lang": lang, "sections": secs}


@router.post("/projects/{pid}/ask")
async def report_ask(pid: str, request: Request, body: Ask) -> dict[str, Any]:
    """Ask about this report: grounded in the engine's own figures (cited, numbers-guarded) and the guidance."""
    from app.copilot.report import answer

    _ai_limit(request, "copilot")
    q = body.question.strip()
    if not q or len(q) > 500:
        raise HTTPException(422, "question must be 1-500 characters")
    return await answer(_project(pid), _result(pid), q, body.lang)


@router.get("/copilot/examples")
def copilot_examples() -> list[str]:
    from app.copilot.service import EXAMPLES

    return EXAMPLES


# ------------------------------------------------------------------ demo, golden, metrics, refdata


class DemoLoad(BaseModel):
    replay: bool = False
    shared: bool = False  # true: reload the shared "demo-shivalik" copy (tests, scripted demos)


_demo_log: dict[str, deque[float]] = defaultdict(deque)
DEMO_LOADS_PER_HOUR = 120  # per address; a room of judges can share one office address


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post("/demo/load")
async def demo_load(request: Request, body: DemoLoad | None = None) -> dict[str, Any]:
    body = body or DemoLoad()
    ip = _client_ip(request)
    window, t = _demo_log[ip], time.time()
    while window and t - window[0] > 3600:
        window.popleft()
    if len(window) >= DEMO_LOADS_PER_HOUR:
        raise HTTPException(429, "too many sample loads from this address; try again later")
    window.append(t)
    if body.shared:
        return await loader.load(force_replay=body.replay)
    try:
        loader.cleanup_old_demos()
    except Exception:  # noqa: S110 - cleanup must never block a judge from loading the sample
        pass
    return await loader.load(force_replay=body.replay, project_id=loader.new_demo_id())


@router.get("/golden")
def golden() -> dict[str, Any]:
    t0 = time.perf_counter()
    out = run_all()
    out["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    out["ran_at"] = now()
    return out


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    path = settings().demo_dir.parent / "backend" / "eval" / "metrics.json"
    alt = settings().demo_dir / "cache" / "metrics.json"
    for p_ in (path, alt):
        if p_.exists():
            return json.loads(p_.read_text())
    return {"status": "not_run", "note": "Run backend/eval/run_extraction_eval.py to produce metrics."}


@router.get("/refdata")
def refdata_summary() -> dict[str, Any]:
    return {"files": refdata.summary(), "doc_types": DOC_TYPES}

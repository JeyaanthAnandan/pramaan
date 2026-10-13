"""Supplier upload links: the Precursor Lever's loop, closed.

The exporter sends one link (WhatsApp, e-mail, or inside the request letter). The rod supplier opens
it on a phone, with no account, and sees only what is asked and why. It uploads its verified CBAM
communication, which joins the exporter's project and runs through the same agents (Classifier,
Extractor, blind SecondReader, checks, Calculator). The line switches from the EU default to verified
actual data and the money moves on the exporter's report. The supplier sees what was read from its
own document, never the exporter's plant data, and the link can only add documents to one line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app import refdata
from app.agents import replay
from app.agents.workflow import execute
from app.config import settings
from app.evidence import blobs
from app.evidence.models import Document, ProcessDef, Project, Run, ShareLink, now
from app.evidence.store import store

router = APIRouter(prefix="/api")

# values the supplier sees back from its own document (with the two-reader status)
SHOWN = ["product_cn", "period", "route", "see", "sefa", "verifier", "verification_ref"]


def public_url(request: Request, path: str) -> str:
    return (settings().public_base_url or str(request.base_url).rstrip("/")) + path


def ensure_link(p: Project, proc: ProcessDef) -> ShareLink:
    """The supplier link for one product line (one per line, reused), and the request marked sent."""
    sr = next((s for s in p.supplier_requests if s.process_id == proc.id), None)
    if sr is None:
        raise HTTPException(404, "no supplier request for this product line")
    link = store().get_share(sr.link_token) if sr.link_token else None
    if link is None or link.kind != "supplier":
        link = ShareLink(
            project_id=p.id,
            kind="supplier",
            process_id=proc.id,
            summary_snapshot={
                "company": p.company,
                "city": p.city,
                "country": p.country,
                "supplier": proc.precursor_supplier,
                "precursor": proc.precursor_name,
                "precursor_cn": refdata.fmt_cn(proc.precursor_cn),
                "product": proc.name,
                "product_cn": proc.cn_display,
                "is_demo": p.is_demo,
            },
        )
        store().put_share(link)
        sr.link_token = link.token
    if sr.status == "not_requested":
        sr.status = "requested"
        sr.updated_at = now()
    store().put_project(p)
    return link


def _link(token: str) -> tuple[ShareLink, Project, ProcessDef]:
    link = store().get_share(token)
    if link is None or link.kind != "supplier":
        raise HTTPException(404, "link not found or expired")
    p = store().get_project(link.project_id)
    proc = next((x for x in p.processes if x.id == link.process_id), None) if p else None
    if p is None or proc is None:
        raise HTTPException(404, "link not found or expired")
    return link, p, proc


def _mine(p: Project, token: str) -> list[Document]:
    return [d for d in store().list_documents(p.id) if d.uploaded_by == f"supplier:{token}"]


def sample_doc(proc: ProcessDef) -> dict[str, Any] | None:
    """The fictional supplier-pack statement for this line's steel input, if there is one."""
    for d in replay.supplier_pack():
        cn = next((f["value_text"] for f in d["fields"] if f["field_key"] == "product_cn"), "")
        if cn.replace(" ", "") == proc.precursor_cn:
            return d
    return None


@router.get("/supplier/{token}")
def supplier_view(token: str) -> dict[str, Any]:
    link, p, proc = _link(token)
    sr = next(s for s in p.supplier_requests if s.process_id == proc.id)
    docs = _mine(p, token)
    ids = {d.id for d in docs}
    values = [
        {
            "field_key": e.field_key,
            "label": e.label or e.field_key,
            "value_text": e.value_text,
            "unit": e.unit,
            "status": e.status,
            "doc_id": e.doc_id,
            "box_2d": e.box_2d,
        }
        for e in store().list_evidence(p.id)
        if e.doc_id in ids and e.field_key in SHOWN
    ]
    values.sort(key=lambda v: SHOWN.index(str(v["field_key"])))
    runs = store().list_runs(p.id)
    latest = max(runs, key=lambda r: r.started_at) if runs else None
    return {
        "request": link.summary_snapshot,
        "status": sr.status,
        "updated_at": sr.updated_at,
        "running": any(r.status == "running" for r in runs),
        # a finished run left the supplier's document unread (no plant data or error text is shown)
        "failed": bool(latest and latest.status != "running" and any(d.state in ("uploaded", "failed") for d in docs)),
        "documents": [
            {"id": d.id, "title": d.title, "state": d.state, "doc_type": d.doc_type, "width": d.width, "height": d.height} for d in docs
        ],
        "values": values,
        "sample_available": p.is_demo and sample_doc(proc) is not None,
    }


@router.get("/supplier/{token}/documents/{doc_id}/image")
def supplier_image(token: str, doc_id: str) -> Response:
    _, p, _ = _link(token)
    d = next((x for x in _mine(p, token) if x.id == doc_id), None)
    if d is None:
        raise HTTPException(404, "document not found")
    return Response(blobs.load(d.uri), media_type=d.content_type, headers={"Cache-Control": "private, max-age=3600"})


def _start(background: BackgroundTasks, p: Project, proc: ProcessDef) -> dict[str, Any]:
    from app.api.routes import runs_settled

    if any(r.status == "running" for r in runs_settled(p.id)):
        raise HTTPException(409, "documents are being processed right now; try again in a minute")
    cfg = settings()
    mode = "live" if (cfg.gemini_configured and cfg.live_runs_enabled) else "replay"
    run = Run(project_id=p.id, mode=mode)  # type: ignore[arg-type]
    store().put_run(run)
    for sr in p.supplier_requests:
        if sr.process_id == proc.id:
            sr.status = "received"
            sr.updated_at = now()
    store().put_project(p)
    background.add_task(_run_and_settle, run, p, mode, proc.id)
    return {"run_id": run.id, "mode": mode, "status": "received"}


async def _run_and_settle(run: Run, p: Project, mode: str, process_id: str) -> None:
    """Only the new documents are read (the others keep their state); then the request is marked
    verified if the line now uses the supplier's verified data, else left as received for review."""
    await execute(run, p, mode, "en", 0.35)
    st = store()
    r = st.get_latest_result(p.id) or {}
    line = next((x for x in r.get("processes", []) if x["id"] == process_id), None)
    pre = (line or {}).get("precursor", {})
    ok = pre.get("data") == "ACTUAL_VERIFIED" and pre.get("status") in {"VERIFIED_2R", "APPROVED"}
    fresh = st.get_project(p.id)
    if fresh is None:
        return
    for sr in fresh.supplier_requests:
        if sr.process_id == process_id:
            sr.status = "verified" if ok else "received"
            sr.updated_at = now()
    st.put_project(fresh)


@router.post("/supplier/{token}/documents")
async def supplier_upload(token: str, request: Request, background: BackgroundTasks, files: list[UploadFile] = File(...)) -> dict[str, Any]:  # noqa: B008
    from app.api.routes import _ai_limit, save_uploads

    _ai_limit(request, "supplier")
    _, p, proc = _link(token)
    if len(_mine(p, token)) >= 10:
        raise HTTPException(413, "this link already holds 10 documents")
    docs = await save_uploads(p.id, files, uploaded_by=f"supplier:{token}", limit=5)
    return {"documents": [d.id for d in docs], **_start(background, p, proc)}


@router.post("/supplier/{token}/sample")
async def supplier_sample(token: str, request: Request, background: BackgroundTasks) -> dict[str, Any]:
    """Fictional sample projects only: send the bundled statement as if the supplier had uploaded it."""
    from app.api.routes import _ai_limit

    _ai_limit(request, "supplier")
    _, p, proc = _link(token)
    d = sample_doc(proc) if p.is_demo else None
    if d is None:
        raise HTTPException(404, "no sample statement for this link")
    name = Path(d["file"]).name
    if any(x.filename == name for x in _mine(p, token)):
        raise HTTPException(409, "the sample statement was already sent")
    path = settings().demo_dir / d["file"]
    import hashlib

    doc = Document(
        id=f"doc_{d['doc_id']}",
        project_id=p.id,
        filename=name,
        content_type="image/jpeg",
        uri=f"demo://{d['file']}",
        width=d["width"],
        height=d["height"],
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        uploaded_by=f"supplier:{token}",
        title=Path(d["file"]).stem,
    )
    store().put_document(doc)
    return {"documents": [doc.id], **_start(background, p, proc)}

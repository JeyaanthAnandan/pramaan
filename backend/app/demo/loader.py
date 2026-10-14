"""M12 demo mode: 'Load sample factory' and 'Process live' for Shivalik Fasteners (SAMPLE).

Load: restores the most recent live Gemini run saved in demo/cache/live_run.json when present
(captured with ``python -m app.demo.capture``); otherwise it replays the bundled ground truth
through the same ADK workflow (mode=replay, clearly labelled).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from app.config import settings
from app.evidence.models import Document, Evidence, ProcessDef, Project, Run, SupplierRequest
from app.evidence.store import store

DEMO_ID = "demo-shivalik"

PROCESSES = [
    ProcessDef(
        id="P1",
        name="Carbon-steel hexagon bolts",
        cn="73181582",
        cn_display="7318 15 82",
        cn_desc="Hexagon screws and bolts, of iron or steel other than stainless",
        precursor_name="Carbon-steel wire rod",
        precursor_cn="72139149",
        precursor_supplier="Northern Wire Rod Mills (SAMPLE)",
        source="sample",
    ),
    ProcessDef(
        id="P2",
        name="Stainless hexagon bolts",
        cn="73181575",
        cn_display="7318 15 75",
        cn_desc="Hexagon screws and bolts, of stainless steel",
        precursor_name="Stainless wire rod",
        precursor_cn="72210010",
        precursor_supplier="Indus Stainless Rods (SAMPLE)",
        source="sample",
    ),
]


def demo_project() -> Project:
    return Project(
        id=DEMO_ID,
        name="Shivalik Fasteners — CBAM 2026 (provisional)",
        company="Shivalik Fasteners Pvt Ltd (SAMPLE — fictional)",
        country="India",
        city="Focal Point, Ludhiana, Punjab",
        year=2026,
        processes=PROCESSES,
        is_demo=True,
        supplier_requests=[
            SupplierRequest(process_id="P1", supplier="Northern Wire Rod Mills (SAMPLE)", status="verified"),
            SupplierRequest(process_id="P2", supplier="Indus Stainless Rods (SAMPLE)", status="not_requested"),
        ],
        what_if={
            "P2": {
                "see": "1.783",
                "sefa": "0.919",
                "source": "If Indus Stainless Rods sends verified data like EC Guidance 5d Example 2 (SEE 1.783) and Table 4-14 (SEFA 0.919)",
            }
        },
    )


def demo_documents(project_id: str) -> list[Document]:
    gt_path = settings().demo_dir / "ground_truth.json"
    gt = json.loads(gt_path.read_text())
    docs = []
    for d in gt["documents"]:
        f = settings().demo_dir / d["file"]
        docs.append(
            Document(
                id=f"doc_{d['doc_id']}",
                project_id=project_id,
                filename=Path(d["file"]).name,
                content_type="image/jpeg",
                uri=f"demo://{d['file']}",
                width=d["width"],
                height=d["height"],
                sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                uploaded_by="demo",
                title=Path(d["file"]).stem,
            )
        )
    return docs


def cache_path() -> Path | None:
    """Prefer a captured live Gemini run; fall back to the captured replay snapshot."""
    for name in ("live_run.json", "replay_run.json"):
        path = settings().demo_dir / "cache" / name
        if path.exists():
            return path
    return None


def reset_demo(project_id: str = DEMO_ID) -> Project:
    st = store()
    st.delete_project(project_id)
    p = demo_project()
    p.id = project_id
    st.put_project(p)
    st.put_documents(demo_documents(p.id))
    return p


def new_demo_id() -> str:
    """Each visitor gets a private copy of the sample, so one judge's approvals never change another's demo."""
    return f"demo-{secrets.token_hex(5)}"


def cleanup_old_demos(max_age_hours: float = 12, limit: int = 25) -> int:
    """Best-effort removal of stale per-visitor sample copies."""
    st = store()
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=max_age_hours)
    removed = 0
    for p in st.list_projects():
        if removed >= limit:
            break
        if p.is_demo and p.id != DEMO_ID and p.id.startswith("demo-"):
            try:
                created = dt.datetime.fromisoformat(p.created_at)
            except ValueError:
                continue
            if created < cutoff:
                st.delete_project(p.id)
                removed += 1
    return removed


def restore_cached(project_id: str = DEMO_ID) -> dict[str, Any] | None:
    path = cache_path()
    if path is None:
        return None
    snap = json.loads(path.read_text())
    st = store()
    p = reset_demo(project_id)
    st.put_documents([Document(**{**d, "project_id": p.id}) for d in snap["documents"]])
    st.put_evidence([Evidence(**{**e, "project_id": p.id}) for e in snap["evidence"]])
    run = Run(**{**snap["run"], "project_id": p.id})
    st.put_run(run)
    from app.agents.workflow import recalculate

    result = recalculate(p.id)
    result["run_id"], result["mode"] = run.id, run.mode
    st.put_result(p.id, run.id, result)
    from app.evidence import ledger

    evidence = st.list_evidence(p.id)
    ledger.append(
        p.id,
        "values_read",
        "Pramaan agents (captured run)" if snap.get("mode") == "live" else "Pramaan (bundled sample)",
        subject=run.id,
        after={"mode": snap.get("mode"), "values": len(evidence), "values_sha256": ledger.values_digest(evidence)},
    )
    source = "cached live Gemini run" if snap.get("mode") == "live" else "replay of bundled ground truth (Gemini not used)"
    return {"project_id": p.id, "run_id": run.id, "source": source, "captured_at": snap.get("captured_at")}


async def load(force_replay: bool = False, project_id: str = DEMO_ID) -> dict[str, Any]:
    if not force_replay:
        cached = restore_cached(project_id)
        if cached:
            return cached
    p = reset_demo(project_id)
    from app.agents.workflow import execute

    run = Run(project_id=p.id, mode="replay")
    store().put_run(run)
    await execute(run, p, "replay")
    return {"project_id": p.id, "run_id": run.id, "source": "replay of bundled ground truth (Gemini not used)"}

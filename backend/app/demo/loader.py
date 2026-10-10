"""M12 demo mode: 'Load sample factory' and 'Process live' for Shivalik Fasteners (SAMPLE).

Load: restores the most recent live Gemini run saved in demo/cache/live_run.json when present
(captured with ``python -m app.demo.capture``); otherwise it replays the bundled ground truth
through the same ADK workflow (mode=replay, clearly labelled).
"""

from __future__ import annotations

import hashlib
import json
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


def cache_path() -> Path:
    return settings().demo_dir / "cache" / "live_run.json"


def reset_demo() -> Project:
    st = store()
    st.delete_project(DEMO_ID)
    p = demo_project()
    st.put_project(p)
    for d in demo_documents(p.id):
        st.put_document(d)
    return p


def restore_cached() -> dict[str, Any] | None:
    path = cache_path()
    if not path.exists():
        return None
    snap = json.loads(path.read_text())
    st = store()
    p = reset_demo()
    for d in snap["documents"]:
        st.put_document(Document(**d))
    st.put_evidence([Evidence(**e) for e in snap["evidence"]])
    run = Run(**snap["run"])
    st.put_run(run)
    from app.agents.workflow import recalculate

    result = recalculate(p.id)
    result["run_id"], result["mode"] = run.id, run.mode
    st.put_result(p.id, run.id, result)
    return {"project_id": p.id, "run_id": run.id, "source": "cached live run", "captured_at": snap.get("captured_at")}


async def load(force_replay: bool = False) -> dict[str, Any]:
    if not force_replay:
        cached = restore_cached()
        if cached:
            return cached
    p = reset_demo()
    from app.agents.workflow import execute

    run = Run(project_id=p.id, mode="replay")
    store().put_run(run)
    await execute(run, p, "replay")
    return {"project_id": p.id, "run_id": run.id, "source": "replay of bundled ground truth (Gemini not used)"}

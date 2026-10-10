"""ADK 2.x workflow graph for one processing run.

    Intake -> Classifier -> Extractor -> SecondReader --(mismatch)--> HumanReview --+
                                               |                                   |
                                               +--------------(all agree)----------+--> ControlChecks
    ControlChecks -> GapFinder (calls the Calculator tool) -> Explainer -> Reporter

Every node emits timeline events (agent, action, input/output summary, duration, model,
tokens) that stream to the browser over SSE and are saved as the run's receipt.
HumanReview does not block: amber values wait for a human tap in the UI (PATCH /evidence),
which triggers a deterministic recalculation.
"""

from __future__ import annotations

import asyncio
import functools
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.adk.workflow import Workflow, node
from google.genai import types

from app.agents import replay
from app.agents.explainer import explain
from app.agents.gap_finder import find_gaps
from app.agents.second_reader import compare, crop
from app.cbam.checks import run_checks
from app.cbam.project import compute
from app.config import settings
from app.evidence import blobs
from app.evidence.models import Document, Evidence, Project, Run, TimelineEvent, now
from app.evidence.store import store

# ------------------------------------------------------------------ live event bus (SSE)


class Bus:
    def __init__(self) -> None:
        self.subs: dict[str, list[asyncio.Queue[TimelineEvent | None]]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue[TimelineEvent | None]:
        q: asyncio.Queue[TimelineEvent | None] = asyncio.Queue()
        self.subs.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[TimelineEvent | None]) -> None:
        if q in self.subs.get(run_id, []):
            self.subs[run_id].remove(q)

    def publish(self, run_id: str, ev: TimelineEvent | None) -> None:
        for q in list(self.subs.get(run_id, [])):
            q.put_nowait(ev)


BUS = Bus()


@dataclass
class RunCtx:
    run: Run
    project: Project
    mode: str  # live | replay
    lang: str = "en"
    seq: int = 0
    stats: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None

    def emit(
        self,
        agent: str,
        action: str,
        *,
        status: str = "done",
        input_summary: str = "",
        output_summary: str = "",
        duration_ms: int | None = None,
        model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        doc_id: str | None = None,
    ) -> None:
        self.seq += 1
        ev = TimelineEvent(
            seq=self.seq,
            agent=agent,
            action=action,
            status=status,  # type: ignore[arg-type]
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=duration_ms,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            doc_id=doc_id,
        )
        self.run.events.append(ev)
        BUS.publish(self.run.id, ev)

    def add_tokens(self, agent: str, tin: int | None, tout: int | None) -> None:
        t = self.stats.setdefault("tokens", {}).setdefault(agent, {"in": 0, "out": 0, "calls": 0})
        t["in"] += tin or 0
        t["out"] += tout or 0
        t["calls"] += 1


RUNS: dict[str, RunCtx] = {}


def _ctx(node_input: Any) -> RunCtx:
    if isinstance(node_input, dict):
        return RUNS[node_input["run_id"]]
    text = node_input.parts[0].text if getattr(node_input, "parts", None) else str(node_input)
    return RUNS[json.loads(text)["run_id"]]


async def _gather_limited(n: int, coros: list[Callable[[], Awaitable[Any]]]) -> list[Any]:
    sem = asyncio.Semaphore(n)

    async def one(f: Callable[[], Awaitable[Any]]) -> Any:
        async with sem:
            return await f()

    return await asyncio.gather(*(one(f) for f in coros), return_exceptions=True)


# ------------------------------------------------------------------ Calculator (ADK function tool)


def cbam_calculator(project_id: str) -> dict[str, Any]:
    """Deterministic CBAM Calculator: computes SEE, SEFA, certificates and buyer cost for a project
    from its evidence records and the official refdata. Returns the result with its calculation tree."""
    st = store()
    project = st.get_project(project_id)
    if project is None:
        raise ValueError(f"unknown project {project_id}")
    return compute(project, st.list_evidence(project_id), st.list_documents(project_id))


CALCULATOR_TOOL = FunctionTool(cbam_calculator)


def recalculate(project_id: str, lang: str = "en") -> dict[str, Any]:
    """Synchronous recompute after a human edit/approval (no LLM involved)."""
    st = store()
    project = st.get_project(project_id)
    assert project is not None
    ev, docs = st.list_evidence(project_id), st.list_documents(project_id)
    result = compute(project, ev, docs)
    result["checks"] = run_checks(project, ev, docs)
    result["gaps"] = find_gaps(project, ev, docs, result)
    prev = st.get_latest_result(project_id) or {}
    from app.agents.explainer import template_sections

    result["explanations"] = template_sections(result)
    result["explainer_meta"] = prev.get("explainer_meta", {"mode": "template"})
    result["run_id"] = prev.get("run_id")
    result["mode"] = prev.get("mode")
    from app.exports.summary import buyer_summary

    result["buyer_summary"] = buyer_summary(project, result)
    st.put_result(project_id, f"recalc-{int(time.time())}", result)
    return result


# ------------------------------------------------------------------ nodes


@node
async def intake(node_input: Any) -> dict[str, Any]:
    c = _ctx(node_input)
    docs = store().list_documents(c.project.id)
    c.emit(
        "Intake",
        "Received documents",
        input_summary=f"{len(docs)} files",
        output_summary=f"mode={c.mode}; " + ", ".join(sorted({d.content_type for d in docs})),
        model=None,
    )
    return {"run_id": c.run.id}


@node
async def classifier(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    st = store()
    docs = [d for d in st.list_documents(c.project.id) if d.state in ("uploaded", "failed") or not d.doc_type]

    async def one(d: Document) -> None:
        t0 = time.perf_counter()
        c.emit("Classifier", "Classifying", status="start", input_summary=d.filename, doc_id=d.id)
        if c.mode == "replay":
            data = replay.classify(d.filename)
            if data is None:
                raise RuntimeError(f"{d.filename}: not a bundled sample; live processing needs Gemini credentials")
            await asyncio.sleep(0.05)
            model, tin, tout = replay.REPLAY_MODEL, None, None
        else:
            from app.agents.readers import classify

            r = await classify(blobs.load(d.uri), d.content_type)
            data, model, tin, tout = r.data, r.model, r.tokens_in, r.tokens_out
            c.add_tokens("Classifier", tin, tout)
        d.doc_type = data["doc_type"]
        d.languages = data.get("languages") or []
        d.title = data.get("title") or d.filename
        d.doc_type_confidence = float(data.get("confidence") or 0)
        d.period = [data.get("period_start") or "", data.get("period_end") or ""]
        d.state = "classified"
        st.put_document(d)
        c.emit(
            "Classifier",
            "Classified",
            input_summary=d.filename,
            output_summary=f"{d.doc_type} · {'/'.join(d.languages)} · conf {d.doc_type_confidence:.2f}",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            model=model,
            tokens_in=tin,
            tokens_out=tout,
            doc_id=d.id,
        )

    res = await _gather_limited(8, [functools.partial(one, d) for d in docs])
    errors = [str(r) for r in res if isinstance(r, Exception)]
    for err in errors:
        c.emit("Classifier", "Failed", status="error", output_summary=err[:300])
    c.stats["classified"] = len(docs) - len(errors)
    return {"run_id": c.run.id}


@node
async def extractor(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    st = store()
    docs = [d for d in st.list_documents(c.project.id) if d.state == "classified"]

    async def one(d: Document) -> int:
        t0 = time.perf_counter()
        c.emit("Extractor", "Extracting fields with regions", status="start", input_summary=f"{d.title} ({d.doc_type})", doc_id=d.id)
        if c.mode == "replay":
            rows = replay.extract(d.filename) or []
            await asyncio.sleep(0.08)
            model, tin, tout = replay.REPLAY_MODEL, None, None
            from app.agents.readers import parse_fields

            fields = parse_fields({"fields": rows}, d.id)
        else:
            from app.agents.readers import extract, parse_fields

            r = await extract(blobs.load(d.uri), d.content_type, d.doc_type or "other", c.project)
            fields, model, tin, tout = parse_fields(r.data, d.id), r.model, r.tokens_in, r.tokens_out
            c.add_tokens("Extractor", tin, tout)
        st.delete_evidence_for_doc(c.project.id, d.id)
        ev = [
            Evidence(
                project_id=c.project.id,
                doc_id=d.id,
                page=f.page,
                field_key=f.field_key,
                label=f.label,
                value_text=f.value_text,
                value_num=f.value_num,
                unit=f.unit,
                box_2d=f.box_2d,
                period=f.period,
                process=f.process,
                item=f.item,
                extractor_model=model,
                status="PENDING",
            )
            for f in fields
        ]
        st.put_evidence(ev)
        d.state = "extracted"
        st.put_document(d)
        boxed = sum(1 for f in fields if f.box_2d)
        c.emit(
            "Extractor",
            "Extracted",
            input_summary=d.title,
            output_summary=f"{len(fields)} values, {boxed} with regions",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            model=model,
            tokens_in=tin,
            tokens_out=tout,
            doc_id=d.id,
        )
        return len(fields)

    res = await _gather_limited(8, [functools.partial(one, d) for d in docs])
    for r in res:
        if isinstance(r, Exception):
            c.emit("Extractor", "Failed", status="error", output_summary=str(r)[:300])
    c.stats["fields"] = sum(r for r in res if isinstance(r, int))
    return {"run_id": c.run.id}


@node
async def second_reader(node_input: dict[str, Any]) -> Event:
    c = _ctx(node_input)
    st = store()
    docs = {d.id: d for d in st.list_documents(c.project.id)}
    todo = [x for x in st.list_evidence(c.project.id) if x.status == "PENDING"]
    model_name = replay.REPLAY_MODEL if c.mode == "replay" else settings().model_lite
    c.emit(
        "SecondReader",
        "Blind second reading of each value (crop only)",
        status="start",
        input_summary=f"{len(todo)} values",
        model=model_name,
    )
    t0 = time.perf_counter()
    image_cache: dict[str, bytes] = {}

    async def one(x: Evidence) -> bool:
        d = docs[x.doc_id]
        if not x.box_2d:
            x.status = "NEEDS_REVIEW"
            x.second_reading = None
            x.notes = "no region returned by the extractor"
            return False
        if d.id not in image_cache:
            image_cache[d.id] = blobs.load(d.uri)
        crop_bytes, padded = crop(image_cache[d.id], x.box_2d)
        if c.mode == "replay":
            r2 = replay.second_read(d.filename, x.model_dump()) or {"value_text": "", "legible": False}
            model = replay.REPLAY_MODEL
        else:
            from app.agents.readers import second_read

            rr = await second_read(crop_bytes, x.field_key, x.unit)
            r2, model = rr.data, rr.model
            c.add_tokens("SecondReader", rr.tokens_in, rr.tokens_out)
        sr = compare(x.value_text, x.value_num, x.unit, r2, model, padded)
        x.second_reader_model = model
        x.second_reading = sr
        x.status = "VERIFIED_2R" if sr.agrees else "NEEDS_REVIEW"
        return sr.agrees

    res = await _gather_limited(16, [functools.partial(one, x) for x in todo])
    st.put_evidence(todo)
    agree = sum(1 for r in res if r is True)
    mismatched = [x for x, r in zip(todo, res, strict=True) if r is not True]
    c.stats["two_reader"] = {"total": len(todo), "agree": agree, "review": len(mismatched)}
    tok = c.stats.get("tokens", {}).get("SecondReader", {})
    c.emit(
        "SecondReader",
        "Compared readings",
        input_summary=f"{len(todo)} crops",
        output_summary=f"{agree} agree (VERIFIED_2R), {len(mismatched)} need review",
        duration_ms=int((time.perf_counter() - t0) * 1000),
        model=model_name,
        tokens_in=tok.get("in"),
        tokens_out=tok.get("out"),
    )
    route = "review" if mismatched else "ok"
    return Event(output={"run_id": c.run.id, "mismatched": [x.id for x in mismatched]}, route=route)  # type: ignore[call-arg]


@node
async def human_review(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    st = store()
    for eid in node_input.get("mismatched", [])[:50]:
        x = st.get_evidence(c.project.id, eid)
        if x:
            c.emit(
                "HumanReview",
                "Needs a human tap",
                status="review",
                input_summary=f"{x.label or x.field_key} {x.period or ''}".strip(),
                output_summary=f"reader 1: {x.value_text} · reader 2: {x.second_reading.reading_value if x.second_reading else '-'}",
                doc_id=x.doc_id,
            )
    return {"run_id": c.run.id}


@node
async def control_checks(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    st = store()
    t0 = time.perf_counter()
    checks = run_checks(c.project, st.list_evidence(c.project.id), st.list_documents(c.project.id))
    c.stats["checks"] = checks
    passed = sum(1 for k in checks if k["status"] == "pass")
    fails = [k["id"] for k in checks if k["status"] == "fail"]
    c.emit(
        "ControlChecks",
        "Cross-document checks (code)",
        input_summary="mass balance, stock, gas, exports, CN",
        output_summary=f"{passed}/{len(checks)} pass" + ("" if not fails else " · fail: " + ", ".join(fails)[:200]),
        duration_ms=int((time.perf_counter() - t0) * 1000),
        model="deterministic",
    )
    return {"run_id": c.run.id}


@node
async def gap_finder(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    st = store()
    t0 = time.perf_counter()
    c.emit(
        "Calculator", "CBAM engine (Decimal, refdata)", status="start", input_summary="evidence + official refdata", model="deterministic"
    )
    result = await CALCULATOR_TOOL.run_async(args={"project_id": c.project.id}, tool_context=None)  # type: ignore[arg-type]
    c.result = result
    sees = ", ".join(f"{p['id']} SEE {float(p['see']):.3f}" for p in result["processes"] if "see" in p)
    c.emit(
        "Calculator",
        "Computed SEE, SEFA, certificates, costs",
        output_summary=f"{sees} · {len(result['calc_tree'])} calc nodes",
        duration_ms=int((time.perf_counter() - t0) * 1000),
        model="deterministic",
    )
    t1 = time.perf_counter()
    gaps = find_gaps(c.project, st.list_evidence(c.project.id), st.list_documents(c.project.id), result)
    c.stats["gaps"] = gaps
    counts = {k: sum(1 for g in gaps if g["status"] == k) for k in ("red", "amber", "green")}
    c.emit(
        "GapFinder",
        "Required-data checklist",
        output_summary=f"{counts['red']} red · {counts['amber']} amber · {counts['green']} green",
        duration_ms=int((time.perf_counter() - t1) * 1000),
        model="deterministic",
    )
    return {"run_id": c.run.id}


@node
async def explainer(node_input: dict[str, Any]) -> dict[str, Any]:
    c = _ctx(node_input)
    t0 = time.perf_counter()
    assert c.result is not None
    live = c.mode == "live"
    sections, meta = await explain(c.result, c.lang, live=live)
    c.stats["explanations"] = sections
    c.stats["explainer_meta"] = meta
    c.emit(
        "Explainer",
        "Plain-language explanation with page citations",
        output_summary=f"{len(sections)} sections · numbers guard: {len(meta.get('rejected', []))} rejected",
        duration_ms=int((time.perf_counter() - t0) * 1000),
        model=settings().model_flash if live else "template",
    )
    return {"run_id": c.run.id}


@node
async def reporter(node_input: dict[str, Any]) -> Event:
    c = _ctx(node_input)
    from app.exports.summary import buyer_summary

    t0 = time.perf_counter()
    assert c.result is not None
    result = dict(c.result)
    result["checks"] = c.stats.get("checks", [])
    result["gaps"] = c.stats.get("gaps", [])
    result["explanations"] = c.stats.get("explanations", [])
    result["explainer_meta"] = c.stats.get("explainer_meta", {})
    result["run_id"] = c.run.id
    result["mode"] = c.mode
    result["buyer_summary"] = buyer_summary(c.project, result)
    store().put_result(c.project.id, c.run.id, result)
    c.emit(
        "Reporter",
        "Report, workbook, verifier pack and buyer summary ready",
        output_summary=f"readiness {float(result['readiness']['score']):.0f}%",
        duration_ms=int((time.perf_counter() - t0) * 1000),
        model="deterministic",
    )
    return Event(message="done")  # type: ignore[call-arg]


WORKFLOW = Workflow(
    name="pramaan_run",
    edges=[
        ("START", intake, classifier, extractor, second_reader),
        (second_reader, {"review": human_review, "ok": control_checks}),
        (human_review, control_checks),
        (control_checks, gap_finder, explainer, reporter),
    ],
)


# ------------------------------------------------------------------ run orchestration


async def execute(run: Run, project: Project, mode: str, lang: str = "en") -> None:
    c = RunCtx(run=run, project=project, mode=mode, lang=lang)
    RUNS[run.id] = c
    st = store()
    t0 = time.perf_counter()
    try:
        runner = InMemoryRunner(agent=WORKFLOW, app_name="pramaan")  # type: ignore[arg-type]
        session = await runner.session_service.create_session(app_name="pramaan", user_id=project.id)
        msg = types.Content(role="user", parts=[types.Part(text=json.dumps({"run_id": run.id}))])
        async for _ in runner.run_async(user_id=project.id, session_id=session.id, new_message=msg):
            pass
        run.status = "done"
    except Exception as exc:  # surface failures honestly in the timeline
        run.status = "error"
        run.error = str(exc)[:500]
        c.emit("Workflow", "Run failed", status="error", output_summary=run.error)
    finally:
        run.finished_at = now()
        tokens = c.stats.get("tokens", {})
        run.metrics = {
            "duration_s": round(time.perf_counter() - t0, 1),
            "documents": len(st.list_documents(project.id)),
            "fields": c.stats.get("fields"),
            "two_reader": c.stats.get("two_reader"),
            "tokens": tokens,
            "tokens_total": sum(v["in"] + v["out"] for v in tokens.values()),
            "mode": mode,
        }
        st.put_run(run)
        BUS.publish(run.id, None)
        RUNS.pop(run.id, None)

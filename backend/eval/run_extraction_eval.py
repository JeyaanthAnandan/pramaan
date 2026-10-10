"""Extraction evaluation on the synthetic Shivalik Fasteners (SAMPLE) document set.

Runs the real ADK workflow on the 24 sample documents and compares every extracted value with
demo/ground_truth.json:
  * field accuracy      - value matches (numbers within 0.5 %, text after normalisation)
  * box hit rate        - predicted region overlaps the true region (IoU >= 0.5)
  * two-reader agreement and human-review rate
  * time per document and total time from upload to report

Usage (from backend/):
  python eval/run_extraction_eval.py --mode live            # needs Gemini credentials
  python eval/run_extraction_eval.py --mode live --capture  # also save the run as the demo cache
  python eval/run_extraction_eval.py --mode replay          # harness self-check, no model

Results: eval/metrics.json (served on the Metrics page) and eval/report.md. Real numbers are
reported even when they miss the target.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.agents.second_reader import norm_text, parse_num  # noqa: E402
from app.cbam.engine import within  # noqa: E402
from app.config import settings  # noqa: E402
from app.evidence.models import Run  # noqa: E402
from app.evidence.store import MemoryStore, set_store, store  # noqa: E402

TARGET_ACCURACY = 0.95
TARGET_SECONDS = 120


def iou(a: list[int] | None, b: list[int] | None) -> float:
    if not a or not b:
        return 0.0
    y0, x0 = max(a[0], b[0]), max(a[1], b[1])
    y1, x1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, y1 - y0) * max(0, x1 - x0)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


def same_value(truth: dict[str, Any], got_text: str, got_num: str | None) -> bool:
    t = parse_num(truth.get("value_num") or "") if truth.get("value_num") else None
    if t is not None:
        g = parse_num(got_num) if got_num else parse_num(got_text)
        return g is not None and within(t, g, Decimal("0.005"))
    return norm_text(truth["value_text"]) == norm_text(got_text)


def key(field_key: str, period: str | None, process: str | None) -> tuple[str, str, str]:
    return (field_key, period or "", process or "")


async def run(mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    set_store(MemoryStore(None))
    from app.agents.workflow import execute
    from app.demo import loader

    p = loader.reset_demo()
    run_ = Run(project_id=p.id, mode=mode)  # type: ignore[arg-type]
    store().put_run(run_)
    t0 = time.perf_counter()
    await execute(run_, p, mode)
    total = time.perf_counter() - t0
    st = store()
    docs = {d.id: d for d in st.list_documents(p.id)}
    ev = st.list_evidence(p.id)
    gt = json.loads((settings().demo_dir / "ground_truth.json").read_text())

    per_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    fields_total = fields_correct = box_hits = 0
    doc_type_correct = 0
    misses: list[dict[str, Any]] = []
    for d in gt["documents"]:
        doc = next((x for x in docs.values() if x.filename == Path(d["file"]).name), None)
        if doc and doc.doc_type == d["doc_type"]:
            doc_type_correct += 1
        got = [e for e in ev if doc and e.doc_id == doc.id]
        by_key: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
        for e in got:
            by_key[key(e.field_key, e.period, e.process)].append(e)
        for f in d["fields"]:
            fields_total += 1
            per_type[d["doc_type"]]["fields"] += 1
            cands = by_key.get(key(f["field_key"], f.get("period"), f.get("process")), [])
            hit = next((c for c in cands if same_value(f, c.value_text, c.value_num)), None)
            if hit:
                fields_correct += 1
                per_type[d["doc_type"]]["correct"] += 1
                if iou(hit.box_2d, f["box_2d"]) >= 0.5:
                    box_hits += 1
                    per_type[d["doc_type"]]["box"] += 1
                if hit.status == "VERIFIED_2R":
                    per_type[d["doc_type"]]["agree"] += 1
            else:
                misses.append(
                    {
                        "doc": d["doc_id"],
                        "field": f["field_key"],
                        "period": f.get("period"),
                        "process": f.get("process"),
                        "truth": f["value_text"],
                        "got": [c.value_text for c in cands][:3],
                    }
                )
    agree = sum(1 for e in ev if e.status == "VERIFIED_2R")
    review = sum(1 for e in ev if e.status == "NEEDS_REVIEW")
    r = st.get_run(p.id, run_.id)
    tokens = (r.metrics or {}).get("tokens_total") if r else None
    n_docs = len(gt["documents"])
    out = {
        "mode": mode,
        "ran_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "models": {
            "extraction": settings().model_flash if mode == "live" else "replay",
            "second_reader": settings().model_lite if mode == "live" else "replay",
        },
        "documents": n_docs,
        "doc_type_accuracy": doc_type_correct / n_docs,
        "fields_total": fields_total,
        "fields_correct": fields_correct,
        "field_accuracy": fields_correct / fields_total if fields_total else 0,
        "box_hit_rate": box_hits / fields_correct if fields_correct else 0,
        "extracted_values": len(ev),
        "two_reader_agreement": agree / len(ev) if ev else 0,
        "review_rate": review / len(ev) if ev else 0,
        "total_seconds": total,
        "seconds_per_doc": total / n_docs,
        "tokens_total": tokens,
        "run_status": r.status if r else None,
        "run_error": r.error if r else None,
        "targets": {"field_accuracy": TARGET_ACCURACY, "total_seconds": TARGET_SECONDS},
        "misses": misses[:40],
    }
    per = {
        k: {
            "fields": v["fields"],
            "accuracy": v["correct"] / v["fields"] if v["fields"] else 0,
            "agreement": v["agree"] / v["correct"] if v["correct"] else 0,
            "box": v["box"] / v["correct"] if v["correct"] else 0,
        }
        for k, v in per_type.items()
    }
    snapshot = {
        "captured_at": out["ran_at"],
        "mode": mode,
        "documents": [d.model_dump() for d in docs.values()],
        "evidence": [e.model_dump() for e in ev],
        "run": r.model_dump() if r else None,
    }
    return {**out, "per_doc_type": per}, snapshot


def write_report(metrics: dict[str, Any]) -> None:
    lines = ["# Extraction evaluation", "", "Synthetic set: 24 photographed SAMPLE documents (demo/), 213 ground-truth fields.", ""]
    for mode in ("live", "replay"):
        m = metrics["runs"].get(mode)
        if not m:
            continue
        ok_acc = "met" if m["field_accuracy"] >= TARGET_ACCURACY else "NOT met"
        ok_t = "met" if m["total_seconds"] < TARGET_SECONDS else "NOT met"
        lines += [
            f"## {mode} run - {m['ran_at']}",
            "",
            f"Models: extraction `{m['models']['extraction']}`, second reader `{m['models']['second_reader']}`"
            + (" (replay of ground truth: harness self-check, not a model score)" if mode == "replay" else ""),
            "",
            "| Metric | Value | Target |",
            "|---|---|---|",
            f"| Document type accuracy | {m['doc_type_accuracy']:.1%} | - |",
            f"| Field accuracy | {m['field_accuracy']:.1%} ({m['fields_correct']}/{m['fields_total']}) | >= 95 % ({ok_acc}) |",
            f"| Region hit rate (IoU >= 0.5, of correct fields) | {m['box_hit_rate']:.1%} | - |",
            f"| Two-reader agreement | {m['two_reader_agreement']:.1%} | - |",
            f"| Human-review rate | {m['review_rate']:.1%} | - |",
            f"| Total time, 24 documents -> report | {m['total_seconds']:.1f} s | < 120 s ({ok_t}) |",
            f"| Time per document | {m['seconds_per_doc']:.2f} s | - |",
            f"| Tokens | {m.get('tokens_total')} | - |",
            "",
        ]
        if m.get("misses"):
            lines += ["Misses (first 40):", "", "| doc | field | period | process | truth | got |", "|---|---|---|---|---|---|"]
            lines += [
                f"| {x['doc']} | {x['field']} | {x['period'] or ''} | {x['process'] or ''} | {x['truth']} | {', '.join(x['got'])} |"
                for x in m["misses"]
            ]
            lines.append("")
    (HERE / "report.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live", "replay"], default="live")
    ap.add_argument("--capture", action="store_true", help="save the run as demo/cache/live_run.json (live mode)")
    args = ap.parse_args()
    if args.mode == "live" and not settings().gemini_configured:
        print("Gemini is not configured (no ADC / service account / GEMINI_API_KEY). Run `gcloud auth application-default login` first.")
        return 2
    result, snapshot = asyncio.run(run(args.mode))
    path = HERE / "metrics.json"
    metrics = json.loads(path.read_text()) if path.exists() else {"runs": {}}
    metrics.setdefault("runs", {})[args.mode] = result
    metrics["per_doc_type"] = result["per_doc_type"] if args.mode == "live" or "per_doc_type" not in metrics else metrics["per_doc_type"]
    metrics["status"] = "ok"
    path.write_text(json.dumps(metrics, indent=1) + "\n")
    write_report(metrics)
    if args.capture and args.mode == "live" and snapshot["run"]:
        cache = settings().demo_dir / "cache" / "live_run.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(snapshot) + "\n")
        print(f"demo cache written: {cache}")
    print(json.dumps({k: v for k, v in result.items() if k not in {"misses", "per_doc_type"}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

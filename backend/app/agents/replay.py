"""Replay backend: reproduces agent outputs for the bundled SAMPLE documents without Gemini.

Used when no Gemini credentials are configured (local dev, CI, and the offline demo). It reads
demo/ground_truth.json - the values and regions exactly as rendered - and is labelled
``replay`` everywhere it appears (timeline, evidence.extractor_model, run.mode) so nobody
mistakes it for a live model run. For a value that is visibly corrected on the page
(struck-through figure), the replayed second reading is the struck value, which reproduces the
ambiguity a blind reader faces; a live run asks Gemini 3.5 Flash-Lite instead.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings

REPLAY_MODEL = "replay:ground-truth"


@lru_cache(maxsize=1)
def truth() -> dict[str, dict[str, Any]]:
    path: Path = settings().demo_dir / "ground_truth.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {Path(d["file"]).name: d for d in data["documents"]}


def for_filename(filename: str) -> dict[str, Any] | None:
    return truth().get(Path(filename).name)


def classify(filename: str) -> dict[str, Any] | None:
    t = for_filename(filename)
    if not t:
        return None
    return {
        "doc_type": t["doc_type"],
        "languages": t["languages"],
        "period_start": t["period"][0],
        "period_end": t["period"][1],
        "title": t["title"],
        "confidence": 1.0,
    }


def extract(filename: str) -> list[dict[str, Any]] | None:
    t = for_filename(filename)
    if not t:
        return None
    out = []
    for f in t["fields"]:
        out.append(
            {k: f.get(k) for k in ["field_key", "value_text", "value_num", "unit", "box_2d", "label", "period", "process", "item"]}
            | {"page": f.get("page", 0)}
        )
    return out


def second_read(filename: str, field: dict[str, Any]) -> dict[str, Any] | None:
    t = for_filename(filename)
    if not t:
        return None
    for f in t["fields"]:
        if (
            f["field_key"] == field["field_key"]
            and f.get("period") == field.get("period")
            and f.get("process") == field.get("process")
            and f["box_2d"] == field.get("box_2d")
        ):
            if f.get("alt"):
                return {
                    "value_text": f["alt"],
                    "value_num": f["alt"],
                    "unit": "",
                    "legible": True,
                    "note": "a crossed-out figure is visible next to the value",
                }
            return {"value_text": f["value_text"], "value_num": f.get("value_num") or "", "unit": "", "legible": True, "note": ""}
    return None

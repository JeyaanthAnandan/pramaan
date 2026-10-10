"""ADK agent for `adk eval`: reads ONE sample document with the live Pramaan readers.

User message = a file name from demo/out (e.g. "scrap-2026-06-to-09.jpg"). The workflow runs the
Classifier, Extractor and blind SecondReader exactly as in production and answers with a compact,
deterministic summary that the eval set compares against ground truth.

    cd backend && adk eval adk_eval/pramaan_reader adk_eval/pramaan_reader.evalset.json --config_file_path adk_eval/test_config.json
(needs Gemini credentials: ADC on Agent Platform, or GEMINI_MODE=api_key + GEMINI_API_KEY)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from google.adk.events import Event  # noqa: E402
from google.adk.workflow import Workflow, node  # noqa: E402

from app.agents.readers import classify, extract, parse_fields, second_read  # noqa: E402
from app.agents.second_reader import compare, crop  # noqa: E402
from app.config import settings  # noqa: E402
from app.evidence.models import Project  # noqa: E402

DEMO_OUT = settings().demo_dir / "out"


def summarize(doc_type: str, fields: list[Any], statuses: dict[int, str]) -> str:
    vals = []
    for i, f in enumerate(fields):
        tag = "/".join(x for x in [f.period, f.process] if x)
        vals.append(
            f"{f.field_key}{'[' + tag + ']' if tag else ''}={f.value_text}{' (review)' if statuses.get(i) == 'NEEDS_REVIEW' else ''}"
        )
    return f"doc_type={doc_type}; values: " + "; ".join(sorted(vals))


@node
async def read_document(node_input: Any) -> Event:
    name = (node_input.parts[0].text if getattr(node_input, "parts", None) else str(node_input)).strip()
    path = (DEMO_OUT / Path(name).name).resolve()
    data = path.read_bytes()
    from app.demo.loader import demo_project

    project: Project = demo_project()
    c = await classify(data, "image/jpeg")
    doc_type = c.data["doc_type"]
    ex = await extract(data, "image/jpeg", doc_type, project)
    fields = parse_fields(ex.data, path.stem)

    async def check(i: int) -> tuple[int, str]:
        f = fields[i]
        if not f.box_2d:
            return i, "NEEDS_REVIEW"
        cb, padded = crop(data, f.box_2d)
        r = await second_read(cb, f.field_key, f.unit)
        return i, "VERIFIED_2R" if compare(f.value_text, f.value_num, f.unit, r.data, r.model, padded).agrees else "NEEDS_REVIEW"

    statuses = dict(await asyncio.gather(*(check(i) for i in range(len(fields)))))
    return Event(message=summarize(doc_type, fields, statuses))  # type: ignore[call-arg]


root_agent = Workflow(name="pramaan_reader", edges=[("START", read_document)])

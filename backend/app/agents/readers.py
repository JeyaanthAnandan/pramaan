"""Classifier, Extractor and SecondReader model calls (Gemini 3.8 Flash / 3.5 Flash-Lite)."""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm import LLMResult, gemini, image_part, text_part
from app.agents.schemas import CLASSIFY_SCHEMA, FIELDS, SECOND_READ_SCHEMA, extraction_schema
from app.config import settings
from app.evidence.models import ExtractedField, Project

CLASSIFY_SYSTEM = (
    "You classify photos of documents from a small steel-goods factory (fasteners, wire, pipes) for EU CBAM "
    "embedded-emissions reporting. Documents may be skewed phone photos, partly handwritten, and may contain "
    "Hindi (Devanagari), Punjabi (Gurmukhi) or Tamil text. Pick exactly one doc_type."
)

DOC_TYPE_GUIDE = {
    "electricity_bill": "utility electricity bill (kWh, kVA)",
    "gas_invoice": "piped natural gas / PNG bill (SCM, GCV, MMBtu)",
    "fuel_invoice": "LPG, diesel, furnace oil or other fuel purchase",
    "precursor_invoice": "purchase invoice for steel input material (wire rod, billets, coils) with HSN/CN code and tonnes",
    "supplier_emissions_statement": "supplier communication of embedded emissions (SEE, SEFA, verification)",
    "production_register": "monthly production register (tonnes produced / consumed)",
    "scrap_log": "scrap or cut-off log (tonnes of scrap)",
    "export_invoice": "commercial/export invoice to a foreign buyer with CN codes and net weight",
    "other": "anything else",
}


def _extract_system(project: Project) -> str:
    procs = "; ".join(
        f"{p.id} = {p.name} (CN {p.cn_display}), made from {p.precursor_name} (CN {p.precursor_cn})" for p in project.processes
    )
    lines = (
        f"Product lines of this factory: {procs}. Set process to the product line id (P1, P2, ...) when a value belongs "
        "to one line; decide from the material, grade, CN code or product name printed next to it. "
        if procs
        else "The factory's product lines are not known: leave process empty. "
    )
    return (
        "You extract values from a photographed factory document for EU CBAM reporting. Return EVERY requested field you can see, "
        "exactly as written (value_text) plus a normalised number (value_num, '.' decimal separator, no thousands separators, Indian "
        "grouping like 1,10,460.80 -> 110460.80). For each value give box_2d = [ymin, xmin, ymax, xmax] normalised to 0-1000 that "
        "tightly encloses only the value itself (not its label). If a figure is crossed out and replaced, report the replacement and "
        "box both. Monthly rows: set period=YYYY-MM. Export invoice line items: set period to the calendar quarter of the invoice date "
        f"(YYYY-Qn). {lines}"
        "Identifiers (invoice, document, verification numbers) and CN/HSN codes: the identifier itself, without dates, labels or "
        "descriptions. Never invent values; skip fields that are not on the document. Do not compute anything."
    )


async def classify(image: bytes, mime: str) -> LLMResult:
    guide = "\n".join(f"- {k}: {v}" for k, v in DOC_TYPE_GUIDE.items())
    return await gemini().json(
        settings().model_flash,
        CLASSIFY_SYSTEM,
        [text_part(f"Document types:\n{guide}\nClassify this document."), image_part(image, mime, "medium")],
        CLASSIFY_SCHEMA,
        thinking_level="low",
    )


async def extract(image: bytes, mime: str, doc_type: str, project: Project) -> LLMResult:
    spec = FIELDS.get(doc_type, {})
    lines = "\n".join(f"- {k}: {desc} [unit: {unit or 'text'}; scope: {scope}]" for k, (desc, unit, scope) in spec.items())
    prompt = f"Document type: {doc_type}.\nFields to extract (field_key: meaning):\n{lines}\nReturn JSON only."
    return await gemini().json(
        settings().model_flash,
        _extract_system(project),
        [text_part(prompt), image_part(image, mime, "high")],
        extraction_schema(),
        thinking_level="medium",
    )


async def second_read(crop_jpeg: bytes, field_key: str, unit_hint: str) -> LLMResult:
    """Blind read: the model sees ONLY the crop and the kind of value, never the first reading."""
    desc = next((d for spec in FIELDS.values() for k, (d, _, _) in spec.items() if k == field_key), field_key)
    prompt = (
        f"This crop comes from a factory document. It should contain one value: {desc}"
        + (f" (usually in {unit_hint})" if unit_hint else "")
        + ". Read it exactly. If a figure is crossed out and replaced, give the final value in value_text and the crossed-out figure in crossed_out. "
        "Give the unit only if it is visible in the crop."
    )
    return await gemini().json(
        settings().model_lite,
        "You are a careful second reader of handwritten and printed figures. You have not seen any other reading.",
        [text_part(prompt), image_part(crop_jpeg, "image/jpeg", "high")],
        SECOND_READ_SCHEMA,
        thinking_level="minimal",
    )


def parse_fields(data: Any, doc_id: str) -> list[ExtractedField]:
    rows = data.get("fields", []) if isinstance(data, dict) else []
    out: list[ExtractedField] = []
    for r in rows:
        try:
            box = r.get("box_2d")
            if box and (len(box) != 4 or not all(0 <= int(v) <= 1000 for v in box)):
                box = None
            out.append(
                ExtractedField(
                    field_key=str(r["field_key"]),
                    value_text=str(r.get("value_text", "")),
                    value_num=(str(r["value_num"]) if r.get("value_num") not in (None, "") else None),
                    unit=str(r.get("unit") or ""),
                    box_2d=[int(v) for v in box] if box else None,
                    page=int(r.get("page") or 0),
                    label=str(r.get("label") or ""),
                    period=(r.get("period") or None),
                    process=(r.get("process") or None),
                    item=(r.get("item") or None),
                    doc_id=doc_id,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def summarize(fields: list[ExtractedField]) -> str:
    keys: dict[str, int] = {}
    for f in fields:
        keys[f.field_key] = keys.get(f.field_key, 0) + 1
    return json.dumps(keys)

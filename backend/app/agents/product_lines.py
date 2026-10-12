"""ProductLines agent: set up an exporter's own project from its documents.

Gemini 3.8 Flash looks at the export invoices (CN codes and descriptions of the goods sold to the
EU) and the purchase invoices / supplier statements for steel inputs, and proposes product lines:
one per exported 8-digit CN code, each linked to the steel input it is made from. Every proposed
code is then checked against the official refdata (app.cbam.products) - the model proposes, code
validates, and a person confirms before the lines count as confirmed.
"""

from __future__ import annotations

from typing import Any

from app.agents.llm import gemini, image_part, text_part
from app.cbam import products
from app.config import settings
from app.evidence import blobs
from app.evidence.models import Document, ProcessDef, Project

SOURCE_TYPES = ("export_invoice", "precursor_invoice", "supplier_emissions_statement")
MAX_DOCS = 8

SYSTEM = (
    "You set up EU CBAM product lines for a small steel-goods factory (fasteners, wire, pipes) from photos of its documents. "
    "Export invoices show the goods sold to the EU with their 8-digit CN codes; purchase invoices and supplier statements show "
    "the steel inputs (wire rod, coils, billets) with supplier, HSN/CN code and grade. Propose one product line per exported "
    "8-digit CN code and link it to the steel input it is made from: match the material (stainless with stainless, carbon or "
    "non-alloy with non-alloy). Copy codes and names exactly as printed; never invent a code that is not on a document. "
    "Indian 8-digit HSN codes on purchase invoices follow the EU CN code for the same goods. Do not compute anything."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "short product name, e.g. 'Stainless hexagon bolts'"},
                    "cn": {"type": "string", "description": "8-digit CN code of the exported good, as printed"},
                    "precursor_name": {"type": "string", "description": "the steel input, e.g. 'Stainless wire rod'"},
                    "precursor_cn": {"type": "string", "description": "8-digit HSN/CN code of the steel input, as printed"},
                    "precursor_supplier": {"type": "string", "description": "supplier of the steel input, as printed"},
                    "doc_ids": {"type": "array", "items": {"type": "string"}, "description": "ids of the documents that show this line"},
                    "rationale": {"type": "string", "description": "one short sentence: which documents show this"},
                },
                "required": ["name", "cn", "precursor_name", "precursor_cn", "precursor_supplier"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["lines"],
}


def pick_documents(documents: list[Document]) -> list[Document]:
    """Export invoices first (they define the goods), then the steel-input documents."""
    rank = {t: i for i, t in enumerate(SOURCE_TYPES)}
    docs = [d for d in documents if d.doc_type in rank and d.content_type.startswith("image/")]
    docs.sort(key=lambda d: (rank[d.doc_type or ""], d.filename))
    out: list[Document] = []
    for t in SOURCE_TYPES:  # at least one of each type when available, then fill up
        out += [d for d in docs if d.doc_type == t][:3]
    return out[:MAX_DOCS]


async def propose(project: Project, documents: list[Document]) -> dict[str, Any]:
    docs = pick_documents(documents)
    if not docs:
        return {"lines": [], "rejected": [], "notes": "No export or steel-input invoices among the classified documents.", "model": None}
    parts: list[dict[str, Any]] = [
        text_part(
            f"Factory country: {project.country}. Documents follow, each preceded by its id and type. Return the product lines as JSON."
        )
    ]
    for d in docs:
        parts.append(text_part(f"Document {d.id} ({d.doc_type}, {d.filename})"))
        parts.append(image_part(blobs.load(d.uri), d.content_type, "high"))
    r = await gemini().json(settings().model_flash, SYSTEM, parts, SCHEMA, thinking_level="medium")
    raw = r.data.get("lines", []) if isinstance(r.data, dict) else []
    lines: list[ProcessDef] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        pdef, errors = products.build_line(item, f"P{len(lines) + 1}", project.country, source="ai")
        if pdef is None:
            rejected.append({"proposal": item, "errors": errors})
        elif pdef.cn in seen:
            rejected.append({"proposal": item, "errors": ["Duplicate CN code: merged with the line above."]})
        else:
            seen.add(pdef.cn)
            lines.append(pdef)
    return {
        "lines": lines,
        "rejected": rejected,
        "notes": (r.data.get("notes") if isinstance(r.data, dict) else "") or "",
        "model": r.model,
        "tokens_in": r.tokens_in,
        "tokens_out": r.tokens_out,
        "documents": [d.id for d in docs],
    }

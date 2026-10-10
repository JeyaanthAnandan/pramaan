"""Build adk_eval/pramaan_reader.evalset.json from demo/ground_truth.json (5 cases)."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GT = json.loads((HERE.parents[1] / "demo" / "ground_truth.json").read_text())
CASES = [
    (
        "skewed_handwritten_scrap_log",
        "scrap-2026-06-to-09",
        "Handwritten Punjabi/Hindi scrap log photographed at 6 degrees; one struck-through figure must go to review.",
    ),
    ("hindi_headed_register", "register-2026-01-to-05", "Production register with Hindi column headings and handwritten monthly tonnes."),
    ("gas_bill_period_and_units", "gas-2026-03", "Gas bill: billing period, SCM, GCV in kcal/SCM and MMBtu (GCV basis)."),
    (
        "rod_invoice_without_supplier_data",
        "rod-ISR-2026-038",
        "Stainless rod invoice with HSN/CN code and mill-test alloy %; no supplier emissions statement exists for this supplier.",
    ),
    ("export_invoice_kg_vs_tonnes", "export-2026-Q2", "Export invoice with net weight in kg per CN line (engine converts to tonnes)."),
]


def expected(d: dict) -> str:
    vals = []
    for f in d["fields"]:
        tag = "/".join(x for x in [f.get("period"), f.get("process")] if x)
        vals.append(f"{f['field_key']}{'[' + tag + ']' if tag else ''}={f['value_text']}{' (review)' if f.get('alt') else ''}")
    return f"doc_type={d['doc_type']}; values: " + "; ".join(sorted(vals))


def main() -> None:
    docs = {d["doc_id"]: d for d in GT["documents"]}
    cases = []
    for eval_id, doc_id, desc in CASES:
        d = docs[doc_id]
        cases.append(
            {
                "eval_id": eval_id,
                "conversation": [
                    {
                        "invocation_id": f"inv-{eval_id}",
                        "user_content": {"role": "user", "parts": [{"text": Path(d["file"]).name}]},
                        "final_response": {"role": "model", "parts": [{"text": expected(d)}]},
                    }
                ],
                "session_input": {"app_name": "pramaan_reader", "user_id": "eval", "state": {"description": desc}},
            }
        )
    out = {
        "eval_set_id": "pramaan_reader_v1",
        "name": "Pramaan document readers",
        "description": "Five brief scenarios on the SAMPLE document set",
        "eval_cases": cases,
    }
    (HERE / "pramaan_reader.evalset.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(cases)} cases written")


if __name__ == "__main__":
    main()

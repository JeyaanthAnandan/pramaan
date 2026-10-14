"""Turn a live run of the test factory (run_live.py's live_evidence.json + live_project.json) into the
backend test fixture: documents, product lines and every reading with its box, nothing else."""

import json
from pathlib import Path

ev = json.load(open("live_evidence.json"))
proj = json.load(open("live_project.json"))
docs = {d["id"]: d for d in proj["documents"]}
rows = []
for e in ev:
    r = {k: e[k] for k in ("field_key", "value_text", "value_num", "unit", "period", "process", "box_2d")}
    r = {"doc": docs[e["doc_id"]]["filename"].rsplit(".", 1)[0], **r}
    if (e.get("second_reading") or {}).get("corrected_from"):
        r["corrected_from"] = e["second_reading"]["corrected_from"]
    rows.append(r)
# 14 Oct 2026: the live reader missed the alloy content on the second stainless invoice; ground truth
for k, v in (("mn_pct", "1.58"), ("cr_pct", "18.20"), ("ni_pct", "8.10"), ("other_alloy_pct", "0.68")):
    if not any(r["doc"] == "rod-NSR-1473" and r["field_key"] == k for r in rows):
        rows.append({"doc": "rod-NSR-1473", "field_key": k, "value_text": v, "value_num": v, "unit": "%", "period": None, "process": "P2", "box_2d": [600, 100, 620, 200]})
fx = {
    "note": "Independent test factory (TEST - fictional): documents in new layouts read by live Gemini, plus any values the reader missed, from the generator's ground truth. Expected results in tests/test_independent_factory.py come from an independent calculator, not the app's engine.",
    "company": "Kaveri Precision Fasteners Pvt Ltd (TEST — fictional)",
    "city": "Coimbatore",
    "months_to": 6,
    "lines": [{k: p.get(k) for k in ("name", "cn", "precursor_name", "precursor_cn", "precursor_supplier")} for p in proj["project"]["processes"]],
    "documents": [{"doc": d["filename"].rsplit(".", 1)[0], "doc_type": d["doc_type"], "width": d["width"], "height": d["height"], "title": d["title"]} for d in proj["documents"]],
    "evidence": rows,
}
out = Path(__file__).resolve().parents[3] / "backend" / "tests" / "fixtures" / "independent_factory.json"
json.dump(fx, open(out, "w"), ensure_ascii=False, indent=0)
print(len(rows), "readings,", len(fx["documents"]), "documents ->", out)

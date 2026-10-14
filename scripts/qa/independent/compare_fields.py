"""Field-level comparison: every value the live readers produced vs the ground truth printed on the documents."""
import json, re
from decimal import Decimal, InvalidOperation
exp = json.load(open("expected.json"))
proj = json.load(open("live_project.json"))
ev = json.load(open("live_evidence.json"))
docs = {d["id"]: d["filename"].rsplit(".", 1)[0] for d in proj["documents"]}
procs = {p["id"]: p for p in proj["project"]["processes"]}
cn2mine = {"73181692": "P1", "73181639": "P2"}
app2mine = {pid: cn2mine.get(p["cn"].replace(" ", ""), "?") for pid, p in procs.items()}
print("app product lines:", {k: (v["name"], v["cn"], v.get("precursor_name"), v.get("precursor_cn"), v.get("source")) for k, v in procs.items()}, "->", app2mine)
def num(s):
    try: return Decimal(re.sub(r"[^\d.\-]", "", str(s).replace(",", "")))
    except (InvalidOperation, TypeError): return None
def norm(s): return re.sub(r"[\s,.\-–—/()]", "", str(s or "")).lower()
got = {}
for e in ev:
    key = (docs.get(e["doc_id"], e["doc_id"]), e["field_key"], e.get("period"), app2mine.get(e.get("process"), e.get("process")))
    got.setdefault(key, []).append(e)
ok = wrong = missing = 0
rows = []
used = set()
for f in exp["fields"]:
    doc, key, val = f[0], f[1], f[2]
    period = f[3] if len(f) > 3 and f[3] != "None" else None
    proc = f[4] if len(f) > 4 else None
    cands = [k for k in got if k[0] == doc and k[1] == key and (period is None or k[2] == period or (k[2] or "").startswith(period[:7])) and (proc is None or k[3] == proc)]
    if not cands:
        missing += 1; rows.append(("MISSING", doc, key, period, proc, val, None, None)); continue
    k = cands[0]; used.add(k)
    e = got[k][0]
    gv = e["value_num"] if e["value_num"] is not None else e["value_text"]
    a, b = num(val), num(e["value_num"] if e["value_num"] is not None else e["value_text"])
    same = (a is not None and b is not None and a == b) if (a is not None and key not in ("invoice_no", "doc_no", "verification_ref", "bill_date", "invoice_date", "period_start", "period_end", "period", "cn_code", "product_cn", "grade")) else (norm(val) == norm(e["value_text"]) or norm(val) in norm(e["value_text"]) or norm(e["value_text"]) in norm(val))
    if same: ok += 1
    else: wrong += 1; rows.append(("WRONG", doc, key, period, proc, val, e["value_text"], e["status"]))
extra = [(k, v[0]["value_text"]) for k, v in got.items() if k not in used]
total = len(exp["fields"])
print(f"\nfields: {ok}/{total} right ({100 * ok / total:.1f} %), {wrong} wrong, {missing} missing, {len(extra)} extra readings")
for r in rows: print("  ", r)
print("\nextra readings (not in the ground truth):")
for k, v in extra[:30]: print("  ", k, "=", v)
st = {}
for e in ev: st[e["status"]] = st.get(e["status"], 0) + 1
print("\nstatuses:", st)
print("needs review:", [(docs.get(e["doc_id"]), e["field_key"], e["value_text"], (e.get("second_reading") or {}).get("reading_value"), (e.get("second_reading") or {}).get("corrected_from")) for e in ev if e["status"] == "NEEDS_REVIEW"])

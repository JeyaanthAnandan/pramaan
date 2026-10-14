"""Expected outputs for the new factory, computed independently (oracle.py + the ground truth in factory.py).
Writes expected.json; nothing here calls or imports the app."""

from __future__ import annotations

import json
from decimal import Decimal as D

import factory as F
import oracle as O

PRICES_2026 = {"2026-Q1": D("75.36"), "2026-Q2": D("75.28"), "2026-Q3": D("82.32")}  # EC price page (raw HTML snapshot)
FX = D("108.3965")

bills = F.gas_bills()
gj = [O.gj_ncv_from_mmbtu(b["mmbtu"]) for b in bills]
prod_total = [F.PRODUCED["P1"][i] + F.PRODUCED["P2"][i] for i in range(6)]
SEC = sum(gj) / sum(prod_total)                          # plant gas per tonne, GJ NCV / t
direct_per_t = SEC * O.EF_NATURAL_GAS / 1000             # t CO2 / t, the same for both lines (mass allocation)

exp: dict = {"plant": {"gas_gj_ncv": [str(round(x, 3)) for x in gj], "sec_gj_per_t": str(round(SEC, 4)), "direct_t_per_t": str(round(direct_per_t, 4))}, "lines": {}}

rod_default = {"carbon": O.india_default("72139149"), "stainless": O.india_default("72210010")}
for pid, ln in F.LINES.items():
    al = sum(F.PRODUCED[pid])
    rod = sum(F.ROD_CONSUMED[ln["rod"]])
    m = rod / al
    cn8 = ln["cn"].replace(" ", "")
    bm_good = O.benchmarks(cn8)
    bm_rod = O.benchmarks(ln["rod_cn"].replace(" ", ""))
    actual_rod = ln["rod"] == "stainless"  # the stainless rod supplier sent a verified statement
    see_rod = F.STATEMENT["see"] if actual_rod else rod_default[ln["rod"]] * (1 + O.MARKUP_2026)
    # SEFA of the precursor: the supplier's actual SEFA, else the column-B benchmark of the rod's default route
    sefa_rod = F.STATEMENT["sefa"] if actual_rod else (bm_rod["B"].get("(C)") or bm_rod["B"].get("(1)"))
    see = direct_per_t + m * see_rod
    sefa = bm_good["A"] + m * sefa_rod
    sefa26 = O.CBAM_FACTOR_2026 * O.CSCF_2026 * sefa
    # buyer's alternative: the good's own default value (+10 %) and its column-B benchmark
    dv_good = O.india_default(cn8)
    see_def = dv_good * (1 + O.MARKUP_2026)
    bm_b_good = bm_good["B"].get("(C)") or bm_good["B"].get("(1)")
    sefa_def26 = O.CBAM_FACTOR_2026 * O.CSCF_2026 * bm_b_good
    q = {}
    for x in F.EXPORTS:
        for line, _desc, net, _g, _c in x["lines"]:
            if line == pid:
                q[x["quarter"]] = q.get(x["quarter"], D(0)) + D(net) / 1000
    exported = sum(q.values())
    price = sum(PRICES_2026[k] * v for k, v in q.items()) / exported
    cost_actual = max(D(0), see - sefa26) * price
    cost_default = max(D(0), see_def - sefa_def26) * price
    buyer = "actual" if cost_actual <= cost_default else "default"
    annual_t = exported * 12 / 6
    saving_t = max(D(0), cost_default - cost_actual)
    exp["lines"][pid] = {
        "name": ln["name"], "cn": ln["cn"], "rod_cn": ln["rod_cn"], "al_t": str(al), "rod_t": str(rod), "m": str(round(m, 4)),
        "see_rod": str(round(see_rod, 4)), "see_direct": str(round(direct_per_t, 4)), "see_precursor": str(round(m * see_rod, 4)), "see": str(round(see, 4)),
        "sefa_rod": str(sefa_rod), "sefa": str(round(sefa, 4)), "sefa_2026": str(round(sefa26, 4)),
        "default_see_2026": str(round(see_def, 4)), "default_sefa_2026": str(round(sefa_def26, 4)),
        "exported_t": str(exported), "exports_by_quarter_t": {k: str(v) for k, v in q.items()}, "price_2026": str(round(price, 4)),
        "cost_actual_eur_t": str(round(cost_actual, 2)), "cost_default_eur_t": str(round(cost_default, 2)), "buyer_pays": buyer,
        "saving_eur_t": str(round(saving_t, 2)), "saving_eur_year": str(round(saving_t * annual_t, 0)), "saving_inr_year": str(round(saving_t * annual_t * FX, 0)),
        "precursor_basis": "actual (verified supplier statement)" if actual_rod else "EU default + 10 % mark-up",
    }

# plant pulse
gpt = [g / p for g, p in zip(gj, prod_total)]
s = sorted(gpt)
median = (s[2] + s[3]) / 2
hot = [i for i, x in enumerate(gpt) if x >= median * D("1.10")]
best = min(range(6), key=lambda i: gpt[i])
pulse = {"gj_per_t": [str(round(x, 3)) for x in gpt], "median": str(round(median, 3)), "hot": [F.MONTHS[i] for i in hot], "best": F.MONTHS[best],
         "hot_pct": [str(round((gpt[i] / median - 1) * 100, 1)) for i in hot]}
for i in hot:
    excess_gj = gj[i] - median * prod_total[i]
    gj_per_scm = D(bills[i]["gcv"]) * D("4.1868") / D(10) ** 6 * O.NCV_PER_GCV
    pulse.setdefault("hot_inr", []).append(str(round(excess_gj / gj_per_scm * bills[i]["rate"], 0)))
    pulse.setdefault("hot_excess_gj", []).append(str(round(excess_gj, 1)))
exp["pulse"] = pulse

# control checks
mb = {}
for pid, ln in F.LINES.items():
    months = [(F.MONTHS[i], F.ROD_CONSUMED[ln["rod"]][i] - F.SCRAP[ln["rod"]][i] - F.PRODUCED[pid][i]) for i in range(6)]
    mb[pid] = {"total_gap_t": str(sum(F.ROD_CONSUMED[ln["rod"]]) - sum(F.SCRAP[ln["rod"]]) - sum(F.PRODUCED[pid])), "monthly_gaps_t": {m: str(g) for m, g in months if g != 0}}
stock = {rod: str(F.STOCK[rod][0] + sum(r["tonnes"] for r in F.ROD_INVOICES if r["rod"] == rod) - F.STOCK[rod][1] - sum(F.ROD_CONSUMED[rod])) for rod in ("carbon", "stainless")}
gas_consistency = [str(round(D(b["scm"]) * D(b["gcv"]) * D("4.1868") / D(10) ** 6 / D("1.055056") - b["mmbtu"], 4)) for b in bills]
exp["checks"] = {"mass_balance": mb, "purchases_vs_consumption_gap_t": stock, "gas_mmbtu_recomputed_minus_printed": gas_consistency,
                 "exports_le_production": {pid: f"{sum(D(n) for x in F.EXPORTS for l, _d, n, _g, _c in x['lines'] if l == pid) / 1000} <= {sum(F.PRODUCED[pid])}" for pid in F.LINES},
                 "supplier": {"P1": "no verified supplier data -> warn", "P2": "verified, covers Jan-Jun -> pass"}, "electricity_kwh": F.ELECTRICITY["kwh"]}
exp["verdict"] = {"saving_eur_year": str(sum(D(v["saving_eur_year"]) for v in exp["lines"].values())), "lines_on_actual": [p for p, v in exp["lines"].items() if v["precursor_basis"].startswith("actual")]}

# field-level ground truth for the readers
gt = []
for b in bills:
    gt += [(b["file"], k, v) for k, v in (("invoice_no", b["no"]), ("bill_date", b["bill_date"]), ("period_start", b["start"]), ("period_end", b["end"]), ("scm", b["scm"]), ("gcv_kcal_per_scm", b["gcv"]), ("mmbtu", b["mmbtu"]), ("rate_inr_per_scm", b["rate"]))]
e = F.ELECTRICITY
gt += [(e["file"], k, v) for k, v in (("invoice_no", e["no"]), ("period_start", e["start"]), ("period_end", e["end"]), ("kwh", e["kwh"]), ("md_kva", e["md_kva"]))]
for r in F.ROD_INVOICES:
    gt += [(r["file"], k, v) for k, v in (("supplier", r["supplier"]), ("invoice_no", r["no"]), ("invoice_date", r["date"]), ("cn_code", r["cn"]), ("grade", r["grade"]), ("tonnes", r["tonnes"]), ("mn_pct", r["mn"]), ("cr_pct", r["cr"]), ("ni_pct", r["ni"]), ("other_alloy_pct", r["other"]))]
st = F.STATEMENT
gt += [(st["file"], k, st[k2]) for k, k2 in (("supplier", "supplier"), ("doc_no", "doc_no"), ("product_cn", "cn"), ("period", "period"), ("route", "route"), ("see", "see"), ("sefa", "sefa"), ("reducing_agent", "reducing_agent"), ("scrap_per_t", "scrap_per_t"), ("pre_consumer_pct", "pre_consumer_pct"), ("verifier", "verifier"), ("verification_ref", "verification_ref"), ("opinion", "opinion"))]
for i, m in enumerate(F.MONTHS):
    gt += [("register-2026-01-to-06", "produced_t", F.PRODUCED["P1"][i], m, "P1"), ("register-2026-01-to-06", "produced_t", F.PRODUCED["P2"][i], m, "P2"),
           ("register-2026-01-to-06", "rod_consumed_t", F.ROD_CONSUMED["carbon"][i], m, "P1"), ("register-2026-01-to-06", "rod_consumed_t", F.ROD_CONSUMED["stainless"][i], m, "P2"),
           ("scrap-2026-01-to-06", "scrap_t", F.SCRAP["carbon"][i], m, "P1"), ("scrap-2026-01-to-06", "scrap_t", F.SCRAP["stainless"][i], m, "P2")]
gt += [("register-2026-01-to-06", "opening_stock_t", F.STOCK["carbon"][0], None, "P1"), ("register-2026-01-to-06", "closing_stock_t", F.STOCK["carbon"][1], None, "P1"),
       ("register-2026-01-to-06", "opening_stock_t", F.STOCK["stainless"][0], None, "P2"), ("register-2026-01-to-06", "closing_stock_t", F.STOCK["stainless"][1], None, "P2")]
for x in F.EXPORTS:
    gt += [(x["file"], "invoice_no", x["no"]), (x["file"], "invoice_date", x["date"]), (x["file"], "buyer", F.BUYER), (x["file"], "country_of_origin", "India")]
    for line, _d, net, _g, _c in x["lines"]:
        gt += [(x["file"], "cn_code", F.LINES[line]["cn"], x["quarter"], line), (x["file"], "net_mass_kg", net, x["quarter"], line)]
exp["fields"] = [[str(v) for v in g] for g in gt]
exp["n_fields"] = len(gt)
json.dump(exp, open("expected.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in exp.items() if k != "fields"}, indent=1, ensure_ascii=False))
print("ground-truth fields:", len(gt))

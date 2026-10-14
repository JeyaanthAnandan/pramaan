"""M10: PDF report (WeasyPrint, HTML -> PDF). Every number is read from the calculation result."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from jinja2 import Environment, select_autoescape

from app.cbam.tree import q
from app.evidence.models import Project

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 18mm 16mm 20mm; @bottom-left { content: "Pramaan · {{ project.company }} · PROVISIONAL — not verified"; font-size: 8pt; color: #666; }
        @bottom-right { content: "page " counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
body { font-family: "Noto Sans", "DejaVu Sans", sans-serif; color: #1c1c1a; font-size: 9.5pt; line-height: 1.45; }
h1 { font-size: 20pt; margin: 0 0 2mm; letter-spacing: -0.3px; } h2 { font-size: 12.5pt; margin: 7mm 0 2mm; border-bottom: 1px solid #ccc; padding-bottom: 1mm; }
.muted { color: #666; } .small { font-size: 8pt; } .banner { background: #fdf3dc; border: 1px solid #e3c27a; padding: 2.5mm 3mm; margin: 3mm 0; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid #ddd; padding: 1.4mm 1.6mm; text-align: left; vertical-align: top; } th { background: #f3f1ea; font-weight: 600; }
td.n, th.n { text-align: right; } .ok { color: #1e7a46; font-weight: 600; } .warn { color: #a86a00; font-weight: 600; } .bad { color: #b42318; font-weight: 600; }
.kpis { display: flex; gap: 3mm; } .kpi { flex: 1; border: 1px solid #ddd; padding: 2.5mm; } .kpi b { font-size: 15pt; display: block; }
.bar { height: 5mm; display: flex; border: 1px solid #bbb; } .bar span { display: block; height: 100%; }
tr, .keep { break-inside: avoid; page-break-inside: avoid; } h2 { break-after: avoid; page-break-after: avoid; } .cn { white-space: nowrap; }
.verdict { display: flex; gap: 3mm; margin: 3mm 0; } .verdict > div { flex: 1; padding: 2.5mm 3mm; border: 1px solid #ddd; }
.verdict .good { background: #eef6f0; border-color: #b9d8c3; } .verdict .reach { background: #eef0f8; border-color: #c4cbe6; }
.verdict b { font-size: 16pt; display: block; letter-spacing: -0.2px; } ol.next { margin: 1mm 0 0 5mm; padding: 0; } ol.next li { margin: 0.8mm 0; }
.hot { background: #fdf3dc; font-weight: 600; }
</style></head><body>
<div class="muted small">EU CBAM · definitive period · iron & steel · {{ result.period_label }}</div>
<h1>CBAM embedded-emissions report</h1>
<div><b>{{ project.company }}</b> — {{ project.city }}, {{ project.country }}</div>
<div class="banner"><b>PROVISIONAL.</b> Year-to-date data, not yet verified by an accredited verifier. Pramaan is not a substitute for an accredited verifier. {% if result.mode %}Mode: {{ result.mode }} · run {{ result.run_id }} · {% endif %}computed {{ result.computed_at }}.</div>
<div class="verdict">
 {% if secured %}<div class="good"><span class="small">Your data saves your buyer</span><b>EUR {{ secured }}</b><span class="small">INR {{ secured_inr }} a year at current volumes</span></div>{% endif %}
 {% if reach %}<div class="reach"><span class="small">More within reach</span><b>+EUR {{ reach }}</b><span class="small">a year if rod suppliers send verified data</span></div>{% endif %}
</div>
{% if next_steps %}<div class="keep"><b>What to do next</b><ol class="next">{% for n in next_steps %}<li>{{ n }}</li>{% endfor %}</ol></div>{% endif %}
<div class="kpis">
 <div class="kpi"><span class="muted small">Readiness (inputs verified or approved)</span><b>{{ readiness }}%</b><span class="small">{{ lines_ready }} of {{ lines_total }} product lines on actual data</span></div>
 {% for p in procs %}<div class="kpi"><span class="muted small">SEE · CN {{ p.cn_display }}</span><b>{{ p.see3 }} t CO2/t</b><span class="small">{{ p.name }}</span></div>{% endfor %}
</div>
<h2>1. Specific embedded emissions per CN group</h2>
<table><thead><tr><th>CN</th><th>Good</th><th class="n">AL (t)</th><th class="n">Own process</th><th class="n">m (t/t)</th><th class="n">Precursor (m × SEE)</th><th class="n">SEE</th><th>Precursor data</th></tr></thead>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td>{{ p.name }}</td><td class="n">{{ p.al }}</td><td class="n">{{ p.direct3 }}</td><td class="n">{{ p.m3 }}</td><td class="n">{{ p.pre3 }}</td><td class="n"><b>{{ p.see3 }}</b></td>
<td>{% if p.precursor.data == "ACTUAL_VERIFIED" %}<span class="ok">actual, verified</span>{% else %}<span class="bad">default + mark-up</span>{% endif %} <span class="small">(SEE {{ p.rod_see3 }})</span><br><span class="small muted">{{ p.precursor.supplier }}{% if p.verified_by %} · {{ p.verified_by }}{% endif %}</span></td></tr>{% endfor %}
</table>
<p class="small muted">t CO2/t of good. Direct emissions only (iron & steel); electricity recorded and excluded. Formula: SEE = AttrEm/AL + Σ m_i × SEE_i (EC Guidance No. 3; Guidance 5d Example 3, p. 53). Scrap and cut-offs carry zero embedded emissions.</p>
{% for p in procs %}<div class="small">{{ p.name }} — contribution: own process {{ p.own_pct }}% · precursor {{ 100 - p.own_pct }}%</div>
<div class="bar"><span style="width: {{ p.own_pct }}%; background:#5b6b7a"></span><span style="width: {{ 100 - p.own_pct }}%; background:{% if p.precursor.data == 'ACTUAL_VERIFIED' %}#7ea08a{% else %}#c8796b{% endif %}"></span></div>{% endfor %}
<h2>2. Free allocation adjustment, certificates and cost (2026 imports)</h2>
<table><thead><tr><th>CN</th><th class="n">SEFA</th><th class="n">SEFA 2026</th><th class="n">Exported (t)</th><th class="n">Certificates (your data)</th><th class="n">Buyer cost, your data (EUR)</th><th class="n">Buyer cost, EU default (EUR)</th><th>Cheaper for the buyer</th></tr></thead>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td class="n">{{ p.sefa3 }}</td><td class="n">{{ p.sefay3 }}</td><td class="n">{{ p.exports }}</td><td class="n">{{ p.certs }}</td><td class="n">{{ p.cost }}</td><td class="n">{{ p.cost_default }}</td><td>{% if p.basis == 'actual' %}<span class="ok">your data</span>{% else %}<span class="warn">EU default</span>{% endif %}<br><span class="small muted">INR {{ p.cost_buyer_inr }}</span></td></tr>{% endfor %}
</table>
<p class="small muted">While a precursor is on its marked-up default value, the good's own EU default can be cheaper for the buyer than the exporter's data. The supplier's verified data is then the lever (section 3).</p>
<p class="small muted">SEFA = BM column A (own process) + Σ m_i × SEFA_i; SEFA_2026 = CBAM factor 0.975 × CSCF 1 × SEFA (Guidance 4; Decision (EU) 2026/1862). Certificates = EE − FAA − carbon price paid (0). Quarterly prices: Q1 €75.36, Q2 €75.28, Q3 €82.32 (EC). FX {{ fx }} INR/EUR (assumption).</p>
<h2>3. Money on the table — buyer's CBAM cost per tonne</h2>
{% for p in procs %}<div class="keep"><div><b>{{ p.name }} (CN {{ p.cn_display }})</b></div>
<table><thead><tr><th>Year</th>{% for s in p.series %}<th class="n">{{ s.year }}</th>{% endfor %}</tr></thead>
<tr><td>Actual data (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.a }}</td>{% endfor %}</tr>
<tr><td>EU default values (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.d }}</td>{% endfor %}</tr>
<tr><td>Difference (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.g }}</td>{% endfor %}</tr>
{% if p.whatif %}<tr><td>If supplier sends verified data</td>{% for s in p.whatif %}<td class="n">{{ s }}</td>{% endfor %}</tr>{% endif %}
</table></div>{% endfor %}
<p class="small muted">Cost per t = max(0, SEE − SEFA_y) × price. Default SEE = DV({{ project.country }}, CN) × (1 + mark-up: 10 % 2026, 20 % 2027, 30 % 2028+). 2027+ price = €{{ proj_price }} (assumption, editable). <b>Myth-buster:</b> some estimates multiply embedded emissions by 2.5 % in 2026. The Commission's formula subtracts a benchmark-based free allocation, so everything above the benchmark is payable: in EC Example 1, 3,690 certificates are due on 15,670 t embedded (23.5 %), not 5 %.</p>
{% if pulse %}<h2>4. Plant pulse — heat-treatment gas per tonne, month by month</h2>
<table><thead><tr><th>Month</th>{% for m in pulse.months %}<th class="n">{{ m.label }}</th>{% endfor %}</tr></thead>
<tr><td>GJ (NCV) per t produced</td>{% for m in pulse.months %}<td class="n{% if m.hot %} hot{% endif %}">{{ m.v }}</td>{% endfor %}</tr>
<tr><td>vs the median month</td>{% for m in pulse.months %}<td class="n{% if m.hot %} hot{% endif %}">{{ m.d }}</td>{% endfor %}</tr></table>
<p class="small">Median month {{ pulse.median }} GJ/t; best month {{ pulse.best }}.{% if pulse.excess_inr %} <b>{{ pulse.hot }} ran hot: INR {{ pulse.excess_inr }} of gas above the median month</b> ({{ pulse.excess_gj }} GJ, {{ pulse.excess_tco2 }} t CO2), at the bill's own rate.{% endif %} Operations insight from the same bills and register; it does not change SEE.</p>{% endif %}
<h2>{{ 5 if pulse else 4 }}. Control checks (EC Guidance No. 2, Step 7)</h2>
<table><thead><tr><th>Check</th><th>Result</th><th>Tolerance</th><th>Status</th></tr></thead>
{% for c in result.checks %}<tr><td>{{ c.name }}<br><span class="small muted">{{ c.formula }}</span></td><td>{{ c.result }}{% if c.note and c.status != 'pass' %}<br><span class="small">{{ c.note }}</span>{% endif %}</td><td>{{ c.tolerance }}</td><td class="{{ {'pass':'ok','fail':'bad','warn':'warn'}.get(c.status,'muted') }}">{{ c.status }}</td></tr>{% endfor %}
</table>
<h2>{{ 6 if pulse else 5 }}. Extra parameters (EC Guidance No. 5d, Table 3-1)</h2>
<table><thead><tr><th>CN</th><th>Reducing agent (precursor)</th><th class="n">Mn %</th><th class="n">Cr %</th><th class="n">Ni %</th><th class="n">Other %</th><th class="n">Scrap t/t</th><th>Pre-consumer</th></tr></thead>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td>{{ p.x.main_reducing_agent.value or 'unknown' }}</td><td class="n">{{ p.x.mn_pct.value }}</td><td class="n">{{ p.x.cr_pct.value }}</td><td class="n">{{ p.x.ni_pct.value }}</td><td class="n">{{ p.x.other_alloy_pct.value }}</td><td class="n">{{ p.x.scrap_t_per_t.value }}</td><td>n/a</td></tr>{% endfor %}
</table>
<h2>{{ 7 if pulse else 6 }}. Assumptions and reference data</h2>
<ul class="small">{% for a in result.assumptions_used %}<li>{{ a }}</li>{% endfor %}</ul>
<p class="small muted">Reference data parsed from official EC files (default values 10 Aug 2026; benchmarks 13 Feb 2026; Guidance 3/4/5d of 14 Aug 2026; certificate prices page) with SHA-256 manifest. Every number in this report opens in the Evidence Lens of the Pramaan app with its source region or reference.</p>
</body></html>"""


def _signed_pct(v: Decimal) -> str:
    """+21 %, -3 %, and 0 % (never "-0 %" for a month a fraction of a percent below the median)."""
    r = v.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return "0 %" if r == 0 else f"{r:+} %"


def _fmt(v: str | Decimal, places: int) -> str:
    return f"{Decimal(v):,.{places}f}"


def context(project: Project, result: dict[str, Any]) -> dict[str, Any]:
    fx = Decimal(result["money"]["fx"]["value"])
    procs = []
    for p in result["processes"]:
        if "see" not in p:
            continue
        tree = result["calc_tree"]
        wi = result["money"]["what_if"].get(p["id"])
        procs.append(
            {
                **p,
                "see3": q(Decimal(p["see"]), 3),
                "direct3": q(Decimal(p["direct"]), 3),
                "m3": q(Decimal(p["m"]), 3),
                "pre3": q(Decimal(tree[f"{p['id']}.rod.contrib"]["value"]), 3),
                "rod_see3": q(Decimal(p["precursor"]["see"]), 3),
                "al": _fmt(p["al_t"], 1),
                "sefa3": q(Decimal(p["sefa"]), 3),
                "sefay3": q(Decimal(p["sefa_y"]), 3),
                "exports": _fmt(p["exports_t"], 1),
                "certs": _fmt(p["certificates_2026"], 1),
                "cost": _fmt(p["cost_2026_eur"], 0),
                "cost_inr": _fmt(Decimal(p["cost_2026_eur"]) * fx, 0),
                "cost_default": _fmt(p["buyer"]["cost_default_eur"], 0),
                "cost_buyer_inr": _fmt(Decimal(p["buyer"]["cost_buyer_eur"]) * fx, 0),
                "basis": p["buyer"]["basis_2026"],
                "own_pct": int((Decimal(tree[f"{p['id']}.own_share"]["value"]) * 100).quantize(Decimal(1))),
                "series": [
                    {"year": s["year"], "a": _fmt(s["actual_eur_t"], 0), "d": _fmt(s["default_eur_t"], 0), "g": _fmt(s["gap_eur_t"], 0)}
                    for s in result["money"]["series"][p["id"]]
                ],
                "whatif": [_fmt(w["eur_t"], 0) for w in wi] if wi else None,
                "x": p["extra_parameters"],
            }
        )
    by_cn = {g["cn"]: g["precursor_data"][0]["status"] for g in (result.get("buyer_summary") or {}).get("goods", [])}
    for x in procs:
        st = by_cn.get(x["cn_display"], "")
        x["verified_by"] = st.split("actual — ", 1)[1] if st.startswith("actual — ") else ""
    secured = sum(
        (
            Decimal(x["buyer"]["annual_gap_eur"])
            for x in procs
            if x["buyer"]["basis_2026"] == "actual" and Decimal(x["buyer"].get("annual_gap_eur") or 0) > 0
        ),
        Decimal(0),
    )
    reach = sum(
        (
            Decimal(x["buyer"]["supplier_saving_annual_eur"])
            for x in procs
            if x["precursor"]["data"] != "ACTUAL_VERIFIED" and Decimal(x["buyer"].get("supplier_saving_annual_eur") or 0) > 0
        ),
        Decimal(0),
    )
    steps = []
    for x in procs:
        b = x["buyer"]
        if x["precursor"]["data"] != "ACTUAL_VERIFIED" and Decimal(b.get("supplier_saving_eur_t") or 0) > 0:
            steps.append(
                f"Ask {x['precursor']['supplier']} for verified data on the {x['precursor']['name'].lower()} ({x['name']}): it would cut the buyer's cost by EUR {_fmt(b['supplier_saving_eur_t'], 0)}/t, about EUR {_fmt(b['supplier_saving_annual_eur'], 0)} a year."
            )
    review = sum(1 for g in result.get("gaps", []) if g.get("group") == "review")
    if review:
        steps.append(
            f"Confirm {review} value{'s' if review > 1 else ''} that need{'' if review > 1 else 's'} a person: the two AI readers "
            "disagree, or the figure was corrected by hand on the page (Close gaps)."
        )
    for x in procs:
        if x["buyer"]["basis_2026"] == "actual" and Decimal(x["buyer"].get("gap_vs_default_eur_t") or 0) > 0:
            steps.append(
                f"Send your verified data for {x['name']} to the buyer: EUR {_fmt(x['buyer']['gap_vs_default_eur_t'], 0)}/t below EU default values."
            )
    gp = (result.get("operations") or {}).get("gas_pulse")
    pulse = None
    if gp:
        import datetime as dt

        def label(m: str) -> str:
            return dt.date(int(m[:4]), int(m[5:7]), 1).strftime("%b")

        hot = [m for m in gp["months"] if m["hot"]]
        pulse = {
            "months": [
                {"label": label(m["month"]), "v": q(Decimal(m["gj_per_t"]), 2), "d": _signed_pct(Decimal(m["delta_pct"])), "hot": m["hot"]}
                for m in gp["months"]
            ],
            "median": q(Decimal(gp["median"]), 2),
            "best": f"{label(gp['best']['month'])} ({q(Decimal(gp['best']['gj_per_t']), 2)} GJ/t)",
            "hot": ", ".join(label(m["month"]) for m in hot),
            "excess_inr": _fmt(gp["excess_inr"], 0) if gp.get("excess_inr") else None,
            "excess_gj": _fmt(gp.get("excess_gj") or "0", 0),
            "excess_tco2": _fmt(gp.get("excess_tco2") or "0", 1),
        }
    return {
        "secured": _fmt(secured, 0) if secured else None,
        "secured_inr": _fmt(secured * fx, 0) if secured else None,
        "reach": _fmt(reach, 0) if reach else None,
        "next_steps": steps,
        "pulse": pulse,
        "project": project,
        "result": result,
        "procs": procs,
        "readiness": q(Decimal(result["readiness"]["score"]), 0),
        "lines_ready": result["readiness"].get("lines_ready", 0),
        "lines_total": result["readiness"].get("lines_total", len(procs)),
        "fx": result["money"]["fx"]["value"],
        "proj_price": result["money"]["projection_price"]["value"],
    }


def html(project: Project, result: dict[str, Any]) -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(TEMPLATE).render(**context(project, result))


def render(project: Project, result: dict[str, Any], lang: str = "en") -> bytes:
    from weasyprint import HTML

    return HTML(string=html(project, result)).write_pdf()  # type: ignore[no-any-return]

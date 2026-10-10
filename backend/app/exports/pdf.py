"""M10: PDF report (WeasyPrint, HTML -> PDF). Every number is read from the calculation result."""

from __future__ import annotations

from decimal import Decimal
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
table, .keep { break-inside: avoid; page-break-inside: avoid; } h2 { break-after: avoid; page-break-after: avoid; } .cn { white-space: nowrap; }
</style></head><body>
<div class="muted small">EU CBAM · definitive period · iron & steel · {{ result.period_label }}</div>
<h1>CBAM embedded-emissions report</h1>
<div><b>{{ project.company }}</b> — {{ project.city }}, {{ project.country }}</div>
<div class="banner"><b>PROVISIONAL.</b> Year-to-date data, not yet verified by an accredited verifier. Pramaan is not a substitute for an accredited verifier. Mode: {{ result.mode }} · run {{ result.run_id }} · computed {{ result.computed_at }}.</div>
<div class="kpis">
 <div class="kpi"><span class="muted small">Readiness (inputs verified or approved)</span><b>{{ readiness }}%</b></div>
 {% for p in procs %}<div class="kpi"><span class="muted small">SEE · CN {{ p.cn_display }}</span><b>{{ p.see3 }} t CO2/t</b><span class="small">{{ p.name }}</span></div>{% endfor %}
</div>
<h2>1. Specific embedded emissions per CN group</h2>
<table><tr><th>CN</th><th>Good</th><th class="n">AL (t)</th><th class="n">Own process</th><th class="n">m (t/t)</th><th class="n">Precursor</th><th class="n">SEE</th><th>Precursor data</th></tr>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td>{{ p.name }}</td><td class="n">{{ p.al }}</td><td class="n">{{ p.direct3 }}</td><td class="n">{{ p.m3 }}</td><td class="n">{{ p.pre3 }}</td><td class="n"><b>{{ p.see3 }}</b></td>
<td>{% if p.precursor.data == "ACTUAL_VERIFIED" %}<span class="ok">actual, verified</span>{% else %}<span class="bad">default + mark-up</span>{% endif %}<br><span class="small muted">{{ p.precursor.supplier }}</span></td></tr>{% endfor %}
</table>
<p class="small muted">t CO2/t of good. Direct emissions only (iron & steel); electricity recorded and excluded. Formula: SEE = AttrEm/AL + Σ m_i × SEE_i (EC Guidance No. 3; Guidance 5d Example 3, p. 53). Scrap and cut-offs carry zero embedded emissions.</p>
{% for p in procs %}<div class="small">{{ p.name }} — contribution: own process {{ p.own_pct }}% · precursor {{ 100 - p.own_pct }}%</div>
<div class="bar"><span style="width: {{ p.own_pct }}%; background:#5b6b7a"></span><span style="width: {{ 100 - p.own_pct }}%; background:{% if p.precursor.data == 'ACTUAL_VERIFIED' %}#7ea08a{% else %}#c8796b{% endif %}"></span></div>{% endfor %}
<h2>2. Free allocation adjustment, certificates and cost (2026 imports)</h2>
<table><tr><th>CN</th><th class="n">SEFA</th><th class="n">SEFA 2026</th><th class="n">Exported (t)</th><th class="n">Certificates</th><th class="n">Buyer cost (EUR)</th><th class="n">Buyer cost (INR)</th></tr>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td class="n">{{ p.sefa3 }}</td><td class="n">{{ p.sefay3 }}</td><td class="n">{{ p.exports }}</td><td class="n">{{ p.certs }}</td><td class="n">{{ p.cost }}</td><td class="n">{{ p.cost_inr }}</td></tr>{% endfor %}
</table>
<p class="small muted">SEFA = BM column A (own process) + Σ m_i × SEFA_i; SEFA_2026 = CBAM factor 0.975 × CSCF 1 × SEFA (Guidance 4; Decision (EU) 2026/1862). Certificates = EE − FAA − carbon price paid (0). Quarterly prices: Q1 €75.36, Q2 €75.28, Q3 €82.32 (EC). FX {{ fx }} INR/EUR (assumption).</p>
<h2>3. Money on the table — buyer's CBAM cost per tonne</h2>
{% for p in procs %}<div class="keep"><div><b>{{ p.name }} (CN {{ p.cn_display }})</b></div>
<table><tr><th>Year</th>{% for s in p.series %}<th class="n">{{ s.year }}</th>{% endfor %}</tr>
<tr><td>Actual data (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.a }}</td>{% endfor %}</tr>
<tr><td>EU default values (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.d }}</td>{% endfor %}</tr>
<tr><td>Difference (EUR/t)</td>{% for s in p.series %}<td class="n">{{ s.g }}</td>{% endfor %}</tr>
{% if p.whatif %}<tr><td>If supplier sends verified data</td>{% for s in p.whatif %}<td class="n">{{ s }}</td>{% endfor %}</tr>{% endif %}
</table></div>{% endfor %}
<p class="small muted">Cost per t = max(0, SEE − SEFA_y) × price. Default SEE = DV(India, CN) × (1 + mark-up: 10 % 2026, 20 % 2027, 30 % 2028+). 2027+ price = €{{ proj_price }} (assumption, editable). <b>Myth-buster:</b> some estimates multiply embedded emissions by 2.5 % in 2026. The Commission's formula subtracts a benchmark-based free allocation, so everything above the benchmark is payable: in EC Example 1, 3,690 certificates are due on 15,670 t embedded (23.5 %), not 5 %.</p>
<h2>4. Control checks (EC Guidance No. 2, Step 7)</h2>
<table><tr><th>Check</th><th>Result</th><th>Tolerance</th><th>Status</th></tr>
{% for c in result.checks %}<tr><td>{{ c.name }}<br><span class="small muted">{{ c.formula }}</span></td><td>{{ c.result }}</td><td>{{ c.tolerance }}</td><td class="{{ {'pass':'ok','fail':'bad','warn':'warn'}.get(c.status,'muted') }}">{{ c.status }}</td></tr>{% endfor %}
</table>
<h2>5. Extra parameters (EC Guidance No. 5d, Table 3-1)</h2>
<table><tr><th>CN</th><th>Reducing agent (precursor)</th><th class="n">Mn %</th><th class="n">Cr %</th><th class="n">Ni %</th><th class="n">Other %</th><th class="n">Scrap t/t</th><th>Pre-consumer</th></tr>
{% for p in procs %}<tr><td class="cn">{{ p.cn_display }}</td><td>{{ p.x.main_reducing_agent.value or 'unknown' }}</td><td class="n">{{ p.x.mn_pct.value }}</td><td class="n">{{ p.x.cr_pct.value }}</td><td class="n">{{ p.x.ni_pct.value }}</td><td class="n">{{ p.x.other_alloy_pct.value }}</td><td class="n">{{ p.x.scrap_t_per_t.value }}</td><td>n/a</td></tr>{% endfor %}
</table>
<h2>6. Assumptions and reference data</h2>
<ul class="small">{% for a in result.assumptions_used %}<li>{{ a }}</li>{% endfor %}</ul>
<p class="small muted">Reference data parsed from official EC files (default values 10 Aug 2026; benchmarks 13 Feb 2026; Guidance 3/4/5d of 14 Aug 2026; certificate prices page) with SHA-256 manifest. Every number in this report opens in the Evidence Lens of the Pramaan app with its source region or reference.</p>
</body></html>"""


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
                "al": _fmt(p["al_t"], 1),
                "sefa3": q(Decimal(p["sefa"]), 3),
                "sefay3": q(Decimal(p["sefa_y"]), 3),
                "exports": _fmt(p["exports_t"], 1),
                "certs": _fmt(p["certificates_2026"], 1),
                "cost": _fmt(p["cost_2026_eur"], 0),
                "cost_inr": _fmt(Decimal(p["cost_2026_eur"]) * fx, 0),
                "own_pct": int((Decimal(tree[f"{p['id']}.own_share"]["value"]) * 100).quantize(Decimal(1))),
                "series": [
                    {"year": s["year"], "a": _fmt(s["actual_eur_t"], 0), "d": _fmt(s["default_eur_t"], 0), "g": _fmt(s["gap_eur_t"], 0)}
                    for s in result["money"]["series"][p["id"]]
                ],
                "whatif": [_fmt(w["eur_t"], 0) for w in wi] if wi else None,
                "x": p["extra_parameters"],
            }
        )
    return {
        "project": project,
        "result": result,
        "procs": procs,
        "readiness": q(Decimal(result["readiness"]["score"]), 0),
        "fx": result["money"]["fx"]["value"],
        "proj_price": result["money"]["projection_price"]["value"],
    }


def html(project: Project, result: dict[str, Any]) -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(TEMPLATE).render(**context(project, result))


def render(project: Project, result: dict[str, Any], lang: str = "en") -> bytes:
    from weasyprint import HTML

    return HTML(string=html(project, result)).write_pdf()  # type: ignore[no-any-return]

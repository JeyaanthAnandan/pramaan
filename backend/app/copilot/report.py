"""Ask about this report: answers about the exporter's own figures, grounded and checked.

Gemini 3.8 Flash gets three kinds of context: FACTS from the deterministic engine (each with the id
of its node in the calculation tree, so the answer's numbers open the Evidence Lens), the most
relevant pages of the EC guidance, and the official default values for the factory's goods and
steel inputs. It cites facts as [F:id] and pages as [Guidance N, p. X] and may not compute: every
number in the answer must already be in the facts or the pages (the Explainer's numbers guard). An
answer that fails the guard is withheld and the facts behind the question are shown instead; without
Gemini the same facts answer it directly.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agents.explainer import _allowed_numbers, _strip_refs, numbers_in
from app.config import settings
from app.evidence.models import Project

log = logging.getLogger("pramaan.copilot")

FACT_RX = re.compile(r"\[F:([A-Za-z0-9_.\-]+)\]")
STOP = {
    "the",
    "a",
    "an",
    "is",
    "my",
    "of",
    "for",
    "to",
    "in",
    "on",
    "and",
    "what",
    "why",
    "how",
    "do",
    "does",
    "i",
    "me",
    "it",
    "are",
    "this",
    "that",
    "which",
    "with",
}


def _d(v: Any) -> Decimal | None:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _eur0(v: Any) -> str:
    d = _d(v)
    return f"{d:,.0f}" if d is not None else ""


def _inr0(v: Decimal) -> str:
    """Indian digit grouping (4,43,93,196), as the report shows rupees."""
    s = f"{v:.0f}"
    neg, s = s.startswith("-"), s.lstrip("-")
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + groups + [tail])
    return ("-" if neg else "") + s


def facts(project: Project, result: dict[str, Any]) -> list[dict[str, Any]]:
    """The report as short, citable facts: id, label, value as the report shows it, unit, lens node."""
    tree = result["calc_tree"]
    out: list[dict[str, Any]] = []

    def node(nid: str, label: str | None = None) -> None:
        n = tree.get(nid)
        if n and n.get("display") not in (None, ""):
            out.append({"id": nid, "label": label or n["label"], "value": str(n["display"]), "unit": n.get("unit") or "", "node": nid})

    def calc(fid: str, label: str, value: str, unit: str = "", lens: str | None = None) -> None:
        if value:
            out.append({"id": fid, "label": label, "value": value, "unit": unit, "node": lens})

    fx = _d(result["money"]["fx"]["value"]) or Decimal(0)
    rd = result["readiness"]
    calc("report.period", "Reporting period", result.get("period_label", ""))
    calc("report.lines_ready", "Product lines that can be declared on actual data", f"{rd['lines_ready']} of {rd['lines_total']}")
    calc("report.fx", "Exchange rate used", str(result["money"]["fx"]["value"]), "INR per EUR")
    secured = Decimal(0)
    reach = Decimal(0)
    for p in result["processes"]:
        if not p.get("see"):
            continue
        pid, name, b, pre = p["id"], p["name"], p["buyer"], p["precursor"]
        calc(f"{pid}.product", f"Product line {pid}", f"{name}, CN {p['cn_display']}")
        node(f"{pid}.see", f"SEE of {name}")
        node(f"{pid}.direct", f"Own process (natural gas) part of SEE — {name}")
        node(f"{pid}.rod.contrib", f"{pre['name']} part of SEE — {name}")
        see, contrib = _d(p["see"]), _d(tree.get(f"{pid}.rod.contrib", {}).get("value"))
        if see and contrib:
            calc(
                f"{pid}.rod.share",
                f"Share of SEE that comes from the {pre['name']} — {name}",
                f"{contrib / see * 100:.0f}",
                "%",
                f"{pid}.rod.contrib",
            )
        basis = (
            "verified data from the supplier" if pre["data"] == "ACTUAL_VERIFIED" else f"EU default for {project.country} + 2026 mark-up"
        )
        calc(f"{pid}.rod.basis", f"How the {pre['name']} ({pre['supplier']}) is valued", basis)
        node(
            pre["see_node"],
            f"SEE of the {pre['name']} used ({'supplier, verified' if pre['data'] == 'ACTUAL_VERIFIED' else 'EU default with 2026 mark-up'})",
        )
        node(f"ref.dv.{p['precursor']['cn']}", f"Official EU default value, {project.country}, {pre['name']} (CN {pre['cn_display']})")
        node(f"ref.dv.{p['cn']}", f"Official EU default value, {project.country}, {name} (CN {p['cn_display']})")
        node(f"{pid}.y2026.default_see", f"Default SEE 2026 incl. mark-up — {name}")
        node(f"{pid}.y2026.cost_actual", f"Buyer's CBAM cost per t in 2026 on your data — {name}")
        node(f"{pid}.y2026.cost_default", f"Buyer's CBAM cost per t in 2026 on EU default values — {name}")
        cost_own, cost_dv = _d(b["actual_eur_t"]), _d(b["default_eur_t"])
        if b["basis_2026"] == "actual":
            pays = "your data"
        elif cost_own is not None and cost_dv is not None and cost_own > cost_dv:
            pays = "the EU default values (cheaper than your data)"
        else:
            pays = "the EU default values"
        calc(f"{pid}.buyer.basis", f"What the buyer declares in 2026 for {name}", pays)
        gap = _d(b.get("annual_gap_eur"))
        if b["basis_2026"] == "actual" and gap and gap > 0:
            secured += gap
            calc(f"{pid}.buyer.annual", f"What your data saves the buyer a year — {name}", _eur0(gap), "EUR/year", b.get("cost_buyer_node"))
            calc(f"{pid}.buyer.annual_inr", f"Same in rupees — {name}", _inr0(gap * fx), "INR/year")
            node(f"{pid}.y2026.gap", f"Saving per t in 2026 against EU default values — {name}")
        sav_t, sav_y = _d(b.get("supplier_saving_eur_t")), _d(b.get("supplier_saving_annual_eur"))
        if pre["data"] != "ACTUAL_VERIFIED" and sav_y and sav_y > 0:
            reach += sav_y
            node(f"whatif.{pid}.y2026.cost", f"Buyer's cost per t in 2026 if {pre['supplier']} sends verified data — {name}")
            calc(f"{pid}.supplier.saving_t", f"Saving per t if {pre['supplier']} sends verified data — {name}", _eur0(sav_t), "EUR/t")
            calc(
                f"{pid}.supplier.saving_year", f"Saving a year if {pre['supplier']} sends verified data — {name}", _eur0(sav_y), "EUR/year"
            )
        node(f"{pid}.exports", f"Exported to the EU in the period — {name}")
        node(f"{pid}.cert.total", f"CBAM certificates for the period's imports on your data — {name}")
        node(f"{pid}.scrap_share", f"Scrap share of rod — {name}")
        ready = rd["by_process"].get(pid, {})
        calc(f"{pid}.ready", f"Can {name} be declared on actual data?", "yes" if ready.get("ready") else "not yet")
    if secured:
        calc("verdict.secured", "What your data saves the buyer a year, all lines", _eur0(secured), "EUR/year")
        calc("verdict.secured_inr", "Same in rupees", _inr0(secured * fx), "INR/year")
    if reach:
        calc("verdict.reach", "More within reach a year if rod suppliers send verified data", _eur0(reach), "EUR/year")
    gp = (result.get("operations") or {}).get("gas_pulse")
    if gp:  # plant pulse: the operations side of the same bills
        node("ops.gas.median", "Median month: heat-treatment gas per tonne produced")
        calc(
            "ops.gas.best",
            f"Best month for gas per tonne ({gp['best']['month']})",
            f"{Decimal(gp['best']['gj_per_t']):.2f}",
            "GJ/t",
            gp["best"]["node"],
        )
        for m in gp["months"]:
            if m["hot"]:
                calc(
                    f"ops.gas.{m['month']}.delta",
                    f"Gas per tonne in {m['month']} against the median month",
                    f"+{Decimal(m['delta_pct']):.1f}",
                    "%",
                    m["node"],
                )
                node(f"ops.gas.{m['month']}.gj_per_t", f"Gas per tonne in {m['month']}")
                node(f"ops.gas.{m['month']}.excess_gj", f"Gas used in {m['month']} above the median month")
                node(f"ops.gas.{m['month']}.excess_inr", f"Cost of that gas in {m['month']}, at the bill's rate")
                node(f"ops.gas.{m['month']}.excess_tco2", f"CO2 from that gas in {m['month']}")
        if not gp["hot_months"]:
            calc("ops.gas.hot", "Months 10 % or more above the median month", "none")
    names = {p.id: p.name for p in project.processes}
    for g in result.get("gaps", []):
        if g["status"] in ("red", "amber"):
            what = g["kind"].replace("_", " ")
            who = names.get(g.get("process") or "", "") or g["params"].get("process", "")
            calc(
                f"gap.{g['id']}",
                "Open item" + (f" — {who}" if who else ""),
                f"{what} ({'missing or on defaults' if g['status'] == 'red' else 'needs a check'})",
            )
    return out


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


INTENTS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("pay", "cost", "buyer", "price", "euro", "eur", "money", "save", "saving", "cheaper"), ("buyer", "saving", "verdict", "cost")),
    (("default", "defaults", "mark", "markup"), ("default", "basis", "rod.see", "ref.dv")),
    (("next", "first", "should", "todo", "priority", "action", "improve"), ("gap.", "supplier.saving", "verdict.reach", "basis")),
    (("see", "emission", "emissions", "carbon", "co2", "intensity"), (".see", "direct", "rod.contrib", "rod.share")),
    (("ready", "declare", "declarable", "verified"), ("ready", "lines_ready", "basis")),
    (("rod", "supplier", "precursor", "wire"), ("rod.", "supplier", "basis")),
    (("gas", "energy", "waste", "wasting", "efficiency", "efficient", "furnace", "fuel", "month", "hot", "operations"), ("ops.gas",)),
]


def relevant(question: str, fs: list[dict[str, Any]], k: int = 8) -> list[dict[str, Any]]:
    """Facts that answer a question, for the no-Gemini path and as the cited-facts panel."""
    q = _tokens(question)
    boosts = [hint for words, hints in INTENTS if q & set(words) for hint in hints]
    lines = {f["id"].split(".")[0] for f in fs if f["id"].endswith(".product") and q & _tokens(f["value"])}  # "stainless" -> P2

    def score(f: dict[str, Any]) -> float:
        s = float(len(q & _tokens(f["label"] + " " + f["value"])))
        s += sum(2 for h in boosts if h in f["id"])
        if lines and f["id"].split(".")[0] in lines:
            s += 1.5
        elif lines and f["id"].split(".")[0].startswith("P"):
            s -= 1
        return s

    ranked = sorted(fs, key=score, reverse=True)
    return [f for f in ranked[:k] if score(f) > 0] or ranked[:4]


def _check(text: str, fs: list[dict[str, Any]], tree: dict[str, Any], pages: list[int]) -> tuple[list[str], list[str]]:
    """Cited fact ids that exist, and the numbers in the answer that are in neither the facts nor the tree."""
    ids = {f["id"] for f in fs}
    cited = [m for m in FACT_RX.findall(text) if m in ids]
    pseudo = {f["id"]: {"value": f["value"].replace(",", ""), "display": f["value"].replace(",", ""), "unit": f["unit"] or "x"} for f in fs}
    allowed = _allowed_numbers({**tree, **pseudo}, [str(p) for p in pages])
    clean = FACT_RX.sub(" ", text)
    bad = [str(n) for n in numbers_in(_strip_refs(clean)) if n not in allowed and n.normalize() not in allowed]
    return cited, bad


def focus(result: dict[str, Any], node: str) -> list[dict[str, Any]]:
    """One number from the Evidence Lens with its formula and its direct inputs, as citable facts."""
    tree = result["calc_tree"]
    n = tree.get(node)
    if not n:
        return []
    out = [
        {
            "id": node,
            "label": n["label"] + (f" (formula: {n['formula']})" if n.get("formula") else ""),
            "value": str(n.get("display") or ""),
            "unit": n.get("unit") or "",
            "node": node,
        }
    ]
    for ch in n.get("children", [])[:12]:
        c = tree.get(ch)
        if c and c.get("display") not in (None, ""):
            src = c.get("source") or {}
            where = (
                f" (read from {src['doc_title']})"
                if src.get("kind") == "evidence" and src.get("doc_title")
                else f" ({src.get('locator')})"
                if src.get("locator")
                else ""
            )
            out.append({"id": ch, "label": c["label"] + where, "value": str(c["display"]), "unit": c.get("unit") or "", "node": ch})
    return out


async def answer(project: Project, result: dict[str, Any], question: str, lang: str = "en", node: str | None = None) -> dict[str, Any]:
    from app.copilot.service import _validate, retrieve

    fs = facts(project, result)
    near = relevant(question, fs)
    if node and (fc := focus(result, node)):  # "explain this number": its formula and inputs come first
        ids = {x["id"] for x in fc}
        fs = fc + [f for f in fs if f["id"] not in ids]
        near = fc + [f for f in near if f["id"] not in ids][: max(0, 8 - len(fc))]
    passages = retrieve(question, k=4)
    base = {"facts": fs, "relevant": [f["id"] for f in near], "passages": passages[:3]}
    if not settings().gemini_configured:
        return {
            **base,
            "mode": "facts",
            "answer": None,
            "note": "no_gemini",
            "citations": [{"doc": p["doc"], "page": p["page"]} for p in passages[:3]],
        }
    from app.agents.llm import gemini, text_part

    lang_line = {"hi": "Answer in Hindi.", "ta": "Answer in Tamil.", "vi": "Answer in Vietnamese."}.get(lang, "Answer in English.")
    system = (
        "You are Pramaan's report assistant for a small Indian steel-goods exporter (bolts, screws, wire). Answer ONLY from FACTS "
        "(this factory's CBAM report, computed by a deterministic engine) and GUIDANCE pages (the EU Commission's guidance). "
        "Cite every number with its fact id in brackets, e.g. [F:P2.see], and method claims as [Guidance N, p. X]. Copy numbers "
        "exactly as written in FACTS: never compute, convert, round or add up numbers yourself. If the facts do not answer the "
        "question, say which document or data is missing. Plain words for a factory owner; keep SEE, SEFA, CBAM and CN in English. "
        "At most 110 words. "
        + lang_line
        + (" Explain how the first fact is worked out from its formula and inputs, step by step." if node else "")
    )
    fact_lines = "\n".join(f"- [F:{f['id']}] {f['label']}: {f['value']}{(' ' + f['unit']) if f['unit'] else ''}" for f in fs)
    ctx = "\n\n".join(f'<page doc="{p["doc"]}" page="{p["page"]}">\n{p["text"]}\n</page>' for p in passages)
    try:
        r = await gemini().text(
            settings().model_flash,
            system,
            [text_part(f"FACTS:\n{fact_lines}\n\nGUIDANCE:\n{ctx}\n\nQuestion: {question}")],
            thinking_level="low",
        )
    except Exception as exc:  # timeout or quota: the facts still answer
        log.warning("report copilot: Gemini did not answer (%s)", str(exc)[:160] or exc.__class__.__name__)
        return {
            **base,
            "mode": "facts",
            "answer": None,
            "note": "no_answer",
            "citations": [{"doc": p["doc"], "page": p["page"]} for p in passages[:3]],
        }
    text = str(r.data or "").strip()
    cited, bad = _check(text, fs, result["calc_tree"], [p["page"] for p in passages])
    cites, invalid = _validate(text, {(p["doc"], p["page"]) for p in passages})
    if bad or not text:
        log.warning("report copilot: answer withheld, numbers not in the report: %s", bad[:5])
        return {
            **base,
            "mode": "facts",
            "answer": None,
            "note": "withheld",
            "rejected_numbers": bad[:5],
            "citations": cites,
            "model": r.model,
        }
    return {
        **base,
        "mode": "grounded",
        "model": r.model,
        "answer": text,
        "cited": cited,
        "citations": cites,
        "invalid_citations": invalid,
        "tokens": {"in": r.tokens_in, "out": r.tokens_out},
    }

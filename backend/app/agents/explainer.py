"""Explainer: short narrative sections with guidance page citations.

Hard rule: it never introduces a number that is not in the calculation tree. Live mode asks
Gemini 3.8 Flash for the narrative from a JSON summary + retrieved guidance passages, then
``guard`` rejects any sentence whose numbers are not in the tree (and falls back to the
template). Replay mode uses the template directly.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUM_RX = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")
ALWAYS_OK = {Decimal(x) for x in ["0", "1", "2", "3", "4", "5", "100"]} | {Decimal(y) for y in range(2020, 2041)}


def _allowed_numbers(tree: dict[str, Any], extra: list[str] | None = None) -> set[Decimal]:
    out: set[Decimal] = set(ALWAYS_OK)
    for n in tree.values():
        for key in ("value", "display"):
            v = n.get(key)
            if v in (None, ""):
                continue
            try:
                d = Decimal(str(v))
            except InvalidOperation:
                continue
            out |= {d, d.quantize(Decimal("0.001")), d.quantize(Decimal("0.01")), d.quantize(Decimal("0.1")), d.quantize(Decimal("1"))}
            if n.get("unit") == "-":  # shares, factors: allow percent form
                out |= {(d * 100).quantize(Decimal("1")), (d * 100).quantize(Decimal("0.1"))}
    for x in extra or []:
        try:
            out.add(Decimal(x))
        except InvalidOperation:
            pass
    return out


def numbers_in(text: str) -> list[Decimal]:
    nums = []
    for m in NUM_RX.finditer(text):
        raw = m.group(0).replace(",", "")
        try:
            nums.append(Decimal(raw))
        except InvalidOperation:
            continue
    return nums


REF_RX = re.compile(
    r"\b(?:sections?|s\.|Tables?|Annex|Article|Art\.|p\.|pp\.|pages?|Guidance(?: No\.)?|No\.|Example|Step|Reg\.|Regulation(?: \(EU\))?)"
    r"\s*[A-Z]?\d+[a-z]?(?:[.\-–/]\d+[a-z]?)*(?:\s*(?:,|and|to|–|-)\s*\d+(?:[.\-–]\d+)*)*",
    re.IGNORECASE,
)
CN_RX = re.compile(r"\bCN\s*\d{4}(?:\s?\d{2}){0,3}\b")
QUARTER_RX = re.compile(r"\b(?:20\d\d-)?Q[1-4]\b")


def _strip_refs(text: str) -> str:
    """Remove citations, CN codes and section references before checking numbers."""
    return QUARTER_RX.sub(" ", CN_RX.sub(" ", REF_RX.sub(" ", text)))


def guard(text: str, tree: dict[str, Any], citations_pages: list[int] | None = None) -> tuple[bool, list[str]]:
    """True if every number in ``text`` exists in the calc tree (or is a page/year/small integer)."""
    allowed = _allowed_numbers(tree, [str(p) for p in (citations_pages or [])])
    bad = [str(n) for n in numbers_in(_strip_refs(text)) if n not in allowed and n.normalize() not in allowed]
    return (not bad), bad


def template_sections(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic narrative; every number is read from the result/tree."""
    tree = result["calc_tree"]

    def disp(nid: str) -> str:
        n = tree.get(nid)
        return n["display"] if n else "?"

    sections = []
    for p in result["processes"]:
        if "see_node" not in p:
            continue
        pid = p["id"]
        pre = p["precursor"]
        own_share = Decimal(tree[pid + ".own_share"]["value"]) * 100
        if pre["data"] == "ACTUAL_VERIFIED":
            pre_txt = (
                f"The wire rod comes from {pre['supplier']} with a verified SEE of {disp(pre['see_node'])} t CO2/t, "
                f"so actual supplier data is used (actual precursor data needs the supplier's verified data, Guidance 3 p. 115)."
            )
        else:
            pre_txt = (
                f"{pre['supplier']} has not sent verified data, so the precursor is valued at the default "
                f"{disp(pre['see_node'])} t CO2/t (country default with the 2026 mark-up, Guidance 3 section 4.10.1). "
                f"This is the Precursor Lever: verified supplier data replaces the default."
            )
        sections.append(
            {
                "process": pid,
                "title": f"{p['name']} — CN {p['cn_display']}",
                "text": (
                    f"Specific embedded emissions are {disp(p['see_node'])} t CO2/t: own process {disp(pid + '.direct')} t CO2/t from natural gas "
                    f"and {disp(pid + '.rod.contrib')} t CO2/t from the wire rod (m = {disp(pid + '.rod.m')} t rod per t of bolts, because cut-offs "
                    f"carry zero embedded emissions). The own process is only {own_share.quantize(Decimal('1'))}% of the total. {pre_txt} "
                    f"Electricity is recorded but not counted: for iron and steel goods only direct emissions count."
                ),
                "citations": [
                    {"doc": "Guidance 5d", "page": 53, "why": "Example 3: screws and nuts from purchased rods"},
                    {"doc": "Guidance 3", "page": 115, "why": "default values and mark-up"},
                ],
            }
        )
    return sections


async def explain(result: dict[str, Any], lang: str = "en", live: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sections = template_sections(result)
    meta: dict[str, Any] = {"mode": "template", "rejected": []}
    tree = result["calc_tree"]
    for s in sections:
        ok, bad = guard(s["text"], tree, [c["page"] for c in s["citations"]])
        if not ok:  # template bug: never ship unverifiable numbers
            raise AssertionError(f"template introduced numbers not in the tree: {bad}")
    if not live:
        return sections, meta
    from app.agents.llm import gemini, text_part
    from app.config import settings

    llm = gemini()
    out = []
    for s in sections:
        prompt = (
            "Rewrite this CBAM explanation for a small Indian factory owner in plain language"
            + (f", in language code '{lang}'" if lang != "en" else "")
            + ". Keep regulatory terms (SEE, SEFA, CBAM, CN) in English. Use ONLY the numbers that appear in the text; do not compute or add numbers. "
            "Keep the page citations. Max 90 words.\n\n" + s["text"]
        )
        r = await llm.text(
            settings().model_flash, "You explain EU CBAM results. Never introduce new numbers.", [text_part(prompt)], thinking_level="low"
        )
        ok, bad = guard(str(r.data), tree, [c["page"] for c in s["citations"]])
        if ok and r.data:
            out.append({**s, "text": str(r.data), "model": r.model})
        else:
            meta["rejected"].append({"process": s["process"], "bad_numbers": bad})
            out.append(s)
    meta["mode"] = "gemini"
    return out, meta

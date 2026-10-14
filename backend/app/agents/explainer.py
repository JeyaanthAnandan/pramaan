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

# Only a Latin letter, digit or dot before a number makes it part of a name (P1, A2-70, M8): a number
# written straight after a Hindi or Tamil word is still a number.
NUM_RX = re.compile(r"(?<![A-Za-z0-9_.])[-+]?\d[\d,]*(?:\.\d+)?")
ALWAYS_OK = {Decimal(x) for x in ["0", "1", "2", "3", "4", "5", "100"]} | {Decimal(y) for y in range(2020, 2041)}
# Devanagari, Gurmukhi, Gujarati, Bengali, Tamil, Telugu, Kannada, Malayalam, Arabic-Indic and Thai digits:
# an answer that writes "२.०४०" is checked like "2.040", never skipped
_SCRIPT_ZEROS = (0x0966, 0x0A66, 0x0AE6, 0x09E6, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0660, 0x06F0, 0x0E50)
DIGITS = str.maketrans({chr(z + i): str(i) for z in _SCRIPT_ZEROS for i in range(10)})


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
    for m in NUM_RX.finditer(text.translate(DIGITS)):
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


def same_numbers(rewrite: str, source: str, must_keep: list[str], pages: list[int]) -> tuple[bool, list[str]]:
    """A rewrite may use only its source's own numbers, and must keep the ones that matter. Checking
    against the whole tree is not enough: it holds 380 figures, and one product line's SEE said as the
    other's would pass (2026-10-14 review)."""
    allowed = set(ALWAYS_OK) | {Decimal(p) for p in pages} | {n.normalize() for n in numbers_in(_strip_refs(source))}
    got = {n.normalize() for n in numbers_in(_strip_refs(rewrite))}
    bad = sorted(str(n) for n in got if n not in allowed)
    bad += [f"missing {k}" for k in must_keep if Decimal(k).normalize() not in got]
    return (not bad), bad


# The deterministic narrative in the four UI languages. Numbers come from the calculation tree and
# are inserted the same way in every language, so the numbers guard holds for all of them; guidance
# references stay in Latin script ("Guidance 3 p. 115") so the guard can recognise them.
TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "actual": "The wire rod comes from {supplier} with a verified SEE of {rod_see} t CO2/t, so actual supplier data is used "
        "(actual precursor data needs the supplier's verified data, Guidance 3 p. 115).",
        "default": "{supplier} has not sent verified data, so the precursor is valued at the default {rod_see} t CO2/t (country "
        "default with the 2026 mark-up, Guidance 3 section 4.10.1). This is the Precursor Lever: verified supplier data replaces the default.",
        "main": "Specific embedded emissions are {see} t CO2/t: own process {direct} t CO2/t from natural gas and {contrib} t CO2/t "
        "from the wire rod (m = {m} t rod per t of product, because cut-offs carry zero embedded emissions). The own process is only "
        "{own}% of the total. {pre} Electricity is recorded but not counted: for iron and steel goods only direct emissions count.",
    },
    "hi": {
        "actual": "वायर रॉड {supplier} से आती है, जिसका सत्यापित SEE {rod_see} t CO2/t है, इसलिए सप्लायर का वास्तविक डेटा उपयोग होता है "
        "(वास्तविक precursor डेटा के लिए सप्लायर का सत्यापित डेटा चाहिए, Guidance 3 p. 115)।",
        "default": "{supplier} ने सत्यापित डेटा नहीं भेजा है, इसलिए precursor का मान default {rod_see} t CO2/t लिया गया है (2026 के "
        "mark-up सहित देश का default, Guidance 3 section 4.10.1)। यही Precursor Lever है: सप्लायर का सत्यापित डेटा default की जगह लेता है।",
        "main": "Specific embedded emissions {see} t CO2/t हैं: प्राकृतिक गैस से अपनी प्रक्रिया के {direct} t CO2/t और वायर रॉड से "
        "{contrib} t CO2/t (m = प्रति टन उत्पाद {m} टन रॉड, क्योंकि कटे टुकड़ों में embedded emissions शून्य होते हैं)। अपनी प्रक्रिया "
        "कुल का केवल {own}% है। {pre} बिजली दर्ज होती है पर गिनी नहीं जाती: लोहा और इस्पात के माल के लिए केवल direct emissions गिने जाते हैं।",
    },
    "ta": {
        "actual": "வயர் ராட் {supplier}-இடமிருந்து வருகிறது; அதன் சரிபார்க்கப்பட்ட SEE {rod_see} t CO2/t, எனவே சப்ளையரின் உண்மையான "
        "தரவு பயன்படுத்தப்படுகிறது (உண்மையான precursor தரவுக்கு சப்ளையரின் சரிபார்க்கப்பட்ட தரவு தேவை, Guidance 3 p. 115).",
        "default": "{supplier} சரிபார்க்கப்பட்ட தரவை அனுப்பவில்லை, எனவே precursor-க்கு default {rod_see} t CO2/t மதிப்பு "
        "பயன்படுத்தப்படுகிறது (2026 mark-up உடன் நாட்டின் default, Guidance 3 section 4.10.1). இதுவே Precursor Lever: சப்ளையரின் "
        "சரிபார்க்கப்பட்ட தரவு default-ஐ மாற்றுகிறது.",
        "main": "Specific embedded emissions {see} t CO2/t: இயற்கை எரிவாயுவிலிருந்து சொந்த செயல்முறை {direct} t CO2/t, வயர் "
        "ராடிலிருந்து {contrib} t CO2/t (m = ஒரு டன் பொருளுக்கு {m} டன் ராட், ஏனெனில் வெட்டுத் துண்டுகளுக்கு embedded emissions "
        "பூஜ்யம்). சொந்த செயல்முறை மொத்தத்தில் {own}% மட்டுமே. {pre} மின்சாரம் பதிவு செய்யப்படுகிறது, ஆனால் கணக்கில் சேர்க்கப்படுவதில்லை: "
        "இரும்பு மற்றும் எஃகுப் பொருட்களுக்கு direct emissions மட்டுமே கணக்கிடப்படும்.",
    },
    "vi": {
        "actual": "Thép cuộn được mua từ {supplier} với SEE đã kiểm định {rod_see} t CO2/t, nên dữ liệu thực tế của nhà cung cấp được "
        "sử dụng (dữ liệu tiền chất thực tế cần dữ liệu đã kiểm định của nhà cung cấp, Guidance 3 p. 115).",
        "default": "{supplier} chưa gửi dữ liệu đã kiểm định, nên tiền chất được tính theo giá trị mặc định {rod_see} t CO2/t (mặc "
        "định quốc gia kèm mức cộng thêm năm 2026, Guidance 3 section 4.10.1). Đây là Precursor Lever: dữ liệu đã kiểm định của nhà "
        "cung cấp sẽ thay thế giá trị mặc định.",
        "main": "Phát thải hàm chứa riêng (SEE) là {see} t CO2/t: quy trình của bạn {direct} t CO2/t từ khí tự nhiên và {contrib} t "
        "CO2/t từ thép cuộn (m = {m} tấn thép cuộn cho mỗi tấn sản phẩm, vì phần cắt bỏ có phát thải hàm chứa bằng không). Quy trình của "
        "bạn chỉ chiếm {own}% tổng số. {pre} Điện được ghi nhận nhưng không tính: với hàng sắt thép chỉ tính phát thải trực tiếp.",
    },
}


def template_sections(result: dict[str, Any], lang: str = "en") -> list[dict[str, Any]]:
    """Deterministic narrative; every number is read from the result/tree."""
    tree = result["calc_tree"]
    tx = TEMPLATES.get(lang, TEMPLATES["en"])

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
        pre_txt = (tx["actual"] if pre["data"] == "ACTUAL_VERIFIED" else tx["default"]).format(
            supplier=pre["supplier"], rod_see=disp(pre["see_node"])
        )
        sections.append(
            {
                "process": pid,
                "title": f"{p['name']} — CN {p['cn_display']}",
                "text": tx["main"].format(
                    see=disp(p["see_node"]),
                    direct=disp(pid + ".direct"),
                    contrib=disp(pid + ".rod.contrib"),
                    m=disp(pid + ".rod.m"),
                    own=own_share.quantize(Decimal("1")),
                    pre=pre_txt,
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
        node = next((p["see_node"] for p in result["processes"] if p["id"] == s["process"]), "")
        see = str(tree.get(node, {}).get("display") or "")
        ok, bad = same_numbers(str(r.data or ""), s["text"], [see] if see else [], [c["page"] for c in s["citations"]])
        if ok and r.data:
            out.append({**s, "text": str(r.data), "model": r.model})
        else:
            meta["rejected"].append({"process": s["process"], "bad_numbers": bad})
            out.append(s)
    meta["mode"] = "gemini"
    return out, meta

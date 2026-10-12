"""USP 2 - blind two-reader check.

For each extracted value we crop its region (padded 15 %) and send ONLY the crop to a
different, cheaper model (Gemini 3.5 Flash-Lite) that never sees the first reading. Numbers
must agree within 0.5 %, units must match after normalisation; text must match after
normalisation. Agreement -> VERIFIED_2R, otherwise NEEDS_REVIEW with both readings. A figure
corrected by hand on the page (crossed out and replaced) is NEEDS_REVIEW even when both agree.
"""

from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

from PIL import Image

from app.cbam.engine import within
from app.evidence.models import SecondReading

PAD = 0.15
NUM_TOL = Decimal("0.005")

UNIT_ALIASES = {
    "mt": "t",
    "t": "t",
    "tonne": "t",
    "tonnes": "t",
    "ton": "t",
    "tons": "t",
    "metric tonne": "t",
    "टन": "t",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "scm": "SCM",
    "sm3": "SCM",
    "standard cubic metre": "SCM",
    "mmbtu": "MMBtu",
    "kcal/scm": "kcal/SCM",
    "kwh": "kWh",
    "units": "kWh",
    "kva": "kVA",
    "%": "%",
    "percent": "%",
    "tco2e/t": "t CO2e/t",
    "t co2e/t": "t CO2e/t",
    "tco2/t": "t CO2e/t",
    "t co2/t": "t CO2e/t",
    "t co2e / t": "t CO2e/t",
    "t/t": "t/t",
    "inr/scm": "INR/SCM",
    "rs/scm": "INR/SCM",
    "rs./scm": "INR/SCM",
    "₹/scm": "INR/SCM",
    "rupees/scm": "INR/SCM",
}


def norm_unit(u: str | None) -> str:
    if not u:
        return ""
    k = re.sub(r"\s+", " ", u.strip().lower().replace("₂", "2"))
    return UNIT_ALIASES.get(k, UNIT_ALIASES.get(k.replace(" ", ""), u.strip()))


def parse_num(s: str | None) -> Decimal | None:
    """Accept '1,10,460.80', '21,192', '0,748' (EU comma decimal) and '15.4'."""
    if s is None:
        return None
    t = s.strip().replace(" ", "").replace(" ", "")
    t = re.sub(r"[^\d,.\-]", "", t)
    if not t or not re.search(r"\d", t):
        return None
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        parts = t.split(",")
        thousands = (len(parts[-1]) == 3 and parts[0].lstrip("-") not in ("", "0")) or len(parts) > 2
        t = t.replace(",", "") if thousands else t.replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def norm_text(s: str | None) -> str:
    return re.sub(r"[\s\-_/.,:;()]+", "", (s or "").casefold())


def crop(image_bytes: bytes, box_2d: list[int]) -> tuple[bytes, list[int]]:
    """Crop the value region with 15 % padding. Returns JPEG bytes and the padded box (0-1000)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    ymin, xmin, ymax, xmax = box_2d
    bh, bw = max(ymax - ymin, 4), max(xmax - xmin, 4)
    py, px = bh * PAD, bw * PAD
    # make sure tiny boxes still give the reader some context
    py, px = max(py, 6), max(px, 6)
    padded = [max(0, int(ymin - py)), max(0, int(xmin - px)), min(1000, int(ymax + py)), min(1000, int(xmax + px))]
    left, top = padded[1] * w // 1000, padded[0] * h // 1000
    right, bottom = max(left + 8, padded[3] * w // 1000), max(top + 8, padded[2] * h // 1000)
    region = img.crop((left, top, right, bottom))
    if region.width < 160:  # upscale small crops for legibility
        f = 160 / region.width
        region = region.resize((int(region.width * f), int(region.height * f)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    region.save(out, format="JPEG", quality=92)
    return out.getvalue(), padded


def compare(first_text: str, first_num: str | None, first_unit: str, second: dict, model: str, crop_box: list[int]) -> SecondReading:
    r2_text = str(second.get("value_text") or "")
    r2_num = parse_num(str(second.get("value_num") or "")) if second.get("value_num") else parse_num(r2_text)
    r2_unit = norm_unit(second.get("unit"))
    n1 = parse_num(first_num) if first_num else parse_num(first_text)
    reason = ""
    if n1 is not None and r2_num is not None:
        agrees = within(n1, r2_num, NUM_TOL)
        delta = str(r2_num - n1)
        if not agrees:
            reason = f"numbers differ: {n1} vs {r2_num}"
    elif n1 is not None:
        agrees, delta = False, None
        reason = "second reader found no number"
    else:
        # the crop is padded, so the second reader may also read a neighbouring line (an address
        # under a name): one of its lines must match the first reading exactly
        first = norm_text(first_text)
        agrees = first == norm_text(r2_text) or (bool(first) and first in {norm_text(ln) for ln in r2_text.splitlines()})
        delta = None
        if not agrees:
            reason = "text differs"
    u1 = norm_unit(first_unit)
    if agrees and r2_unit and u1 and r2_unit != u1:
        agrees = False
        reason = f"units differ: {u1} vs {r2_unit}"
    if not second.get("legible", True):
        agrees = False
        reason = reason or "second reader marked the crop illegible"
    # a figure corrected by hand on the page goes to a person even when both readers agree: which
    # value counts is the owner's call (and a verifier asks about every manual correction)
    crossed = str(second.get("crossed_out") or "").strip()
    corrected_from = crossed if crossed and norm_text(crossed) != norm_text(r2_text) else None
    if corrected_from and agrees:
        reason = f"corrected on the document: {corrected_from} crossed out"
    return SecondReading(
        reading_value=r2_text,
        reading_unit=r2_unit or None,
        agrees=agrees,
        delta=delta,
        model=model,
        crop_box=crop_box,
        reason=reason or ("agree" if agrees else ""),
        corrected_from=corrected_from,
    )

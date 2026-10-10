"""USP 2 - the blind two-reader comparison rules."""

from __future__ import annotations

import io
from decimal import Decimal

from PIL import Image

from app.agents.second_reader import compare, crop, norm_unit, parse_num


def test_parse_num_formats() -> None:
    assert parse_num("1,10,460.80") == Decimal("110460.80")
    assert parse_num("21,192") == Decimal("21192")
    assert parse_num("0,748") == Decimal("0.748")
    assert parse_num("15.4 t") == Decimal("15.4")
    assert parse_num("SAMPLE") is None


def test_units_normalise() -> None:
    assert norm_unit("MT") == "t"
    assert norm_unit("tonnes") == "t"
    assert norm_unit("mmbtu") == "MMBtu"
    assert norm_unit("tCO2e/t") == "t CO2e/t"


def test_numbers_within_half_percent_agree() -> None:
    sr = compare("803.543", "803.543", "MMBtu", {"value_text": "803.54", "legible": True}, "m", [0, 0, 1, 1])
    assert sr.agrees


def test_numbers_beyond_tolerance_disagree() -> None:
    sr = compare("15.4", "15.4", "t", {"value_text": "13.4", "value_num": "13.4", "legible": True}, "m", [0, 0, 1, 1])
    assert not sr.agrees and "differ" in sr.reason and sr.delta == "-2.0"


def test_unit_mismatch_fails() -> None:
    sr = compare("280000", "280000", "kg", {"value_text": "280,000", "unit": "t", "legible": True}, "m", [0, 0, 1, 1])
    assert not sr.agrees and "units differ" in sr.reason


def test_unit_not_visible_in_crop_is_not_a_mismatch() -> None:
    sr = compare("280000", "280000", "kg", {"value_text": "280,000", "unit": "", "legible": True}, "m", [0, 0, 1, 1])
    assert sr.agrees


def test_text_fields_compare_normalised() -> None:
    assert compare("SF/EXP/2627/009", None, "", {"value_text": "SF EXP 2627 009", "legible": True}, "m", [0, 0, 1, 1]).agrees


def test_illegible_crop_needs_review() -> None:
    assert not compare("12", "12", "t", {"value_text": "12", "legible": False}, "m", [0, 0, 1, 1]).agrees


def test_crop_pads_fifteen_percent() -> None:
    img = Image.new("RGB", (1000, 1000), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data, padded = crop(buf.getvalue(), [400, 400, 500, 600])
    assert padded == [385, 370, 515, 630]
    assert Image.open(io.BytesIO(data)).width >= 160

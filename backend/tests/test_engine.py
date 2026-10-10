"""Unit tests for the deterministic engine and refdata selection rules."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from app import refdata
from app.cbam import engine as e


def test_decimal_only() -> None:
    with pytest.raises(e.EngineError):
        e.fuel_emissions_t(3.5, D("56.1"))  # type: ignore[arg-type]


def test_negative_inputs_rejected() -> None:
    with pytest.raises(e.EngineError):
        e.see(D("10"), D("-1"), [])
    with pytest.raises(e.EngineError):
        e.see(D("0"), D("1"), [])


def test_scrap_makes_mass_ratio_above_one() -> None:
    assert e.mass_ratio(D("1500"), D("1275")) > 1


def test_certificates_floor_at_zero_and_flag() -> None:
    r = e.certificates([e.ImportLine(D("10"), D("0.5"), D("1.2"))])
    assert r.certificates == 0 and r.floored and r.raw < 0


def test_cost_per_tonne_floor() -> None:
    c = e.cost_per_tonne(D("1.0"), D("1.5"), D("80"))
    assert c.cost_eur_per_t == 0 and c.floored


def test_cost_per_tonne_formula() -> None:
    c = e.cost_per_tonne(D("2.039"), D("1.461"), D("82.32"))
    assert c.payable_t_per_t == D("0.578")
    assert c.cost_eur_per_t == D("0.578") * D("82.32")


def test_carbon_price_deduction() -> None:
    r = e.certificates([e.ImportLine(D("100"), D("2"), D("1"))], carbon_price_deduction_t=D("10"))
    assert r.certificates == D("90")


@pytest.mark.parametrize("year,markup", [(2026, "0.1"), (2027, "0.2"), (2028, "0.3"), (2034, "0.3")])
def test_markups_from_refdata(year: int, markup: str) -> None:
    assert refdata.year_params(year)["default_markup"].value == D(markup)


@pytest.mark.parametrize(
    "year,factor",
    [
        (2026, "0.975"),
        (2027, "0.95"),
        (2028, "0.9"),
        (2029, "0.775"),
        (2030, "0.515"),
        (2031, "0.39"),
        (2032, "0.265"),
        (2033, "0.14"),
        (2034, "0"),
    ],
)
def test_cbam_factor_schedule(year: int, factor: str) -> None:
    assert refdata.year_params(year)["cbam_factor"].value == D(factor)


def test_cscf_official_until_2030_then_preliminary() -> None:
    assert refdata.year_params(2030)["cscf"].status == "official"
    assert refdata.year_params(2031)["cscf"].status == "preliminary"
    assert refdata.year_params(2026)["cscf"].value == 1


def test_default_see_with_markup() -> None:
    dv = refdata.default_value("India", "73181582").value
    assert e.default_see(dv, D("0.1")) == dv * D("1.1")


def test_default_value_country_fallback() -> None:
    r = refdata.default_value("Viet Nam", "72210010")
    assert r.extra["fallback"] is True and r.extra["country_table"] == "Other Countries and Territories"


def test_default_value_unknown_country_uses_other_countries() -> None:
    r = refdata.default_value("Atlantis", "7318 15 82")
    assert r.extra["country_table"] == "Other Countries and Territories"


def test_benchmark_period_selection() -> None:
    assert refdata.benchmark("73181575", "B", 2027).value == D("1.154")  # (1) 2026-27
    assert refdata.benchmark("73181575", "B", 2028).value == D("1.116")  # (2) 2028-30


def test_benchmark_requires_route_when_ambiguous() -> None:
    with pytest.raises(refdata.RefdataError):
        refdata.benchmark("73181582", "B", 2026)
    assert refdata.benchmark("73181582", "B", 2026, route="(C)").value == D("1.364")


def test_quarter_prices() -> None:
    assert refdata.quarter_price(2026, 1).value == D("75.36")
    assert refdata.quarter_price(2026, 3).value == D("82.32")
    q4 = refdata.quarter_price(2026, 4)
    assert q4.status == "assumption"


def test_unit_conversions() -> None:
    gj = e.gj_from_scm(D("1000"), D("9500"), D("4.1868"))
    assert gj == D("39.7746")
    assert e.ncv_from_gcv(D("100"), D("0.9")) == D("90.0")
    assert e.within(D("100"), D("100.4"), D("0.005"))
    assert not e.within(D("100"), D("101"), D("0.005"))

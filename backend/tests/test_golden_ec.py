"""Golden tests: the engine must reproduce EC Guidance No. 5d (14 Aug 2026), section 4.

The build is not done until these pass. Tolerance: +/-0.002 t CO2/t for SEE/SEFA (EC
tables round intermediates to 3 decimals) and the stated tolerance for certificates.
Known inconsistencies in Example 2 are documented in docs/EC_EXAMPLE_NOTES.md and are
deliberately NOT used as tests.
"""

from __future__ import annotations

import pytest

from app.cbam.golden import CASES, run_all


def _assert_case(case_id: str) -> None:
    result = CASES[case_id].run()
    failures = [c for c in result["checks"] if not c["pass"]]
    assert not failures, f"{case_id} failed: {failures}"


def test_g1_example3_carbon_screws_see() -> None:
    """G1 - Guidance 5d s.4.3, Tables 4-12/4-13, p. 53: AL 17,000 t, rod 20,000 t (SEE 1.567),
    gas 3.5 GJ/t at 56.1 t/TJ -> direct 0.196, precursor 1.843, SEE 2.039."""
    _assert_case("G1")


def test_g2_example3_high_alloy_screws_see() -> None:
    """G2 - Guidance 5d s.4.3, Tables 4-12/4-13, p. 53: AL 8,200 t, rod 10,000 t (SEE 1.783)
    -> precursor 2.175, SEE 2.371."""
    _assert_case("G2")


def test_g3_example1_sefa_rails() -> None:
    """G3 - Guidance 5d s.4.1, Table 4-6 p. 43 and p. 44: 0.057 + 1.042 x 1.156 = 1.261;
    x 0.95 (2027) x CSCF 1 = 1.198."""
    _assert_case("G3")


def test_g4_example1_certificates_rails() -> None:
    """G4 - Guidance 5d s.4.1, p. 44: 10,000 t x 1.567 = 15,670; FAA 11,980; 3,690 certificates."""
    _assert_case("G4")


def test_g5_example2_certificates_pipes() -> None:
    """G5 - Guidance 5d s.4.2, Table 4-11 and p. 51: SEFA 0.867; 100 t -> FAA 82.4, 95.9 certificates."""
    _assert_case("G5")


def test_g6_example1_sefa_sheets_bars() -> None:
    """G6 - Guidance 5d s.4.1, Table 4-6, p. 43: sheets 1.248, bars 1.242."""
    _assert_case("G6")


def test_g7_example3_sefa_screws() -> None:
    """G7 (additional) - Guidance 5d s.4.3, Table 4-14, p. 54: SEFA 1.499 (carbon), 1.159 (stainless)."""
    _assert_case("G7")


def test_g8_refdata_matches_guidance() -> None:
    """G8 (additional) - benchmarks and the natural-gas EF used in the examples equal the values
    parsed from the official benchmark file and Methodology Act Annex II s.G."""
    _assert_case("G8")


def test_run_all_reports_every_case() -> None:
    out = run_all()
    assert out["all_pass"] is True
    assert [c["id"] for c in out["cases"]] == [f"G{i}" for i in range(1, 9)]


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_case_cites_a_page_or_table(case_id: str) -> None:
    src = CASES[case_id].source
    assert "p." in src or "Table" in src or "Annex" in src

"""Deterministic CBAM engine (definitive period, iron & steel).

Formulas follow EC Guidance No. 3 (embedded emissions), No. 4 (free allocation
adjustment) and No. 5d (iron and steel, section 4 worked examples). All arithmetic is
``Decimal``; rounding happens only for display. The LLM agents never compute these numbers:
they call the Calculator tool, which wraps this module.

    AttrEm_p = sum_f AD_f x NCV_f x EF_f x OxF_f              (t CO2, direct only)
    SEE_p    = AttrEm_p / AL_p + sum_i m_i x SEE_i            (m_i = M_i / AL_p)
    SEFA_g   = BM_colA(own process) + sum_i m_i x SEFA_i
    SEFA_g,y = CBAMfactor_y x CSCF_y x SEFA_g
    Certificates = sum EE_g - sum FAA_g - carbon price deduction  (floored at 0)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, getcontext

getcontext().prec = 34

D = Decimal
ZERO = D(0)
GJ_PER_TJ = D(1000)


class EngineError(ValueError):
    pass


def _pos(name: str, v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        raise EngineError(f"{name} must be Decimal, got {type(v).__name__}")
    if v < 0:
        raise EngineError(f"{name} must be >= 0, got {v}")
    return v


# ---------------------------------------------------------------- direct emissions


def fuel_emissions_t(energy_gj_ncv: Decimal, ef_t_per_tj: Decimal, oxf: Decimal = D(1)) -> Decimal:
    """Source-stream emissions: AD (GJ, NCV basis) x EF (t CO2/TJ) x OxF."""
    _pos("energy_gj_ncv", energy_gj_ncv)
    _pos("ef_t_per_tj", ef_t_per_tj)
    return energy_gj_ncv / GJ_PER_TJ * ef_t_per_tj * oxf


# ---------------------------------------------------------------- SEE


@dataclass(frozen=True)
class PrecursorUse:
    mass_t: Decimal
    see: Decimal
    name: str = ""


@dataclass(frozen=True)
class SEEResult:
    al_t: Decimal
    direct_specific: Decimal
    precursor_specific: Decimal
    see: Decimal
    m: tuple[Decimal, ...] = field(default_factory=tuple)
    precursor_contrib: tuple[Decimal, ...] = field(default_factory=tuple)


def mass_ratio(precursor_mass_t: Decimal, al_t: Decimal) -> Decimal:
    _pos("precursor_mass_t", precursor_mass_t)
    if al_t <= 0:
        raise EngineError("activity level must be > 0")
    return precursor_mass_t / al_t


def see(al_t: Decimal, attributed_emissions_t: Decimal, precursors: Sequence[PrecursorUse]) -> SEEResult:
    """Specific embedded emissions of a production process (Guidance 3 eq. for complex goods)."""
    if al_t <= 0:
        raise EngineError("activity level must be > 0")
    _pos("attributed_emissions_t", attributed_emissions_t)
    direct = attributed_emissions_t / al_t
    ms = tuple(mass_ratio(p.mass_t, al_t) for p in precursors)
    contrib = tuple(m * _pos("precursor see", p.see) for m, p in zip(ms, precursors, strict=True))
    pre = sum(contrib, ZERO)
    return SEEResult(al_t, direct, pre, direct + pre, ms, contrib)


def default_see(default_value: Decimal, markup: Decimal) -> Decimal:
    """Default SEE including the year's mark-up (Guidance 3 s.4.10.1: 10 % 2026, 20 % 2027, 30 % 2028+)."""
    return _pos("default_value", default_value) * (D(1) + _pos("markup", markup))


# ---------------------------------------------------------------- SEFA and certificates


@dataclass(frozen=True)
class PrecursorSEFA:
    m: Decimal
    sefa: Decimal
    name: str = ""


def sefa(bm_col_a: Decimal, precursors: Sequence[PrecursorSEFA]) -> Decimal:
    """Specific free allocation of a good (Guidance 4 s.2.2): own-process BM (column A) plus precursors."""
    total = _pos("bm_col_a", bm_col_a)
    for p in precursors:
        total += _pos("m", p.m) * _pos("sefa_i", p.sefa)
    return total


def sefa_year(sefa_g: Decimal, cbam_factor: Decimal, cscf: Decimal) -> Decimal:
    """SEFA adjusted for the year of import: CBAM factor x CSCF x SEFA_g."""
    return _pos("sefa_g", sefa_g) * _pos("cbam_factor", cbam_factor) * _pos("cscf", cscf)


@dataclass(frozen=True)
class ImportLine:
    mass_t: Decimal
    see: Decimal
    sefa_y: Decimal
    label: str = ""


@dataclass(frozen=True)
class CertificateResult:
    embedded_t: Decimal
    faa_t: Decimal
    carbon_price_deduction_t: Decimal
    raw: Decimal
    certificates: Decimal
    floored: bool


def certificates(lines: Sequence[ImportLine], carbon_price_deduction_t: Decimal = ZERO) -> CertificateResult:
    """CBAM certificates to surrender: sum EE - sum FAA - carbon price deduction, floored at 0."""
    ee = sum((_pos("mass_t", line.mass_t) * _pos("see", line.see) for line in lines), ZERO)
    faa = sum((line.mass_t * _pos("sefa_y", line.sefa_y) for line in lines), ZERO)
    raw = ee - faa - _pos("carbon_price_deduction_t", carbon_price_deduction_t)
    return CertificateResult(ee, faa, carbon_price_deduction_t, raw, max(raw, ZERO), raw < 0)


@dataclass(frozen=True)
class CostPerTonne:
    payable_t_per_t: Decimal
    cost_eur_per_t: Decimal
    floored: bool


def cost_per_tonne(see_g: Decimal, sefa_g_y: Decimal, price_eur: Decimal) -> CostPerTonne:
    """Buyer's CBAM cost per tonne of good: (SEE - SEFA_y) x certificate price, floored at 0."""
    payable = _pos("see", see_g) - _pos("sefa_y", sefa_g_y)
    floored = payable < 0
    payable = max(payable, ZERO)
    return CostPerTonne(payable, payable * _pos("price", price_eur), floored)


# ---------------------------------------------------------------- unit conversions


def gj_gcv_from_mmbtu(mmbtu: Decimal, gj_per_mmbtu: Decimal) -> Decimal:
    return _pos("mmbtu", mmbtu) * _pos("gj_per_mmbtu", gj_per_mmbtu)


def gj_from_scm(scm: Decimal, gcv_kcal_per_scm: Decimal, kj_per_kcal: Decimal) -> Decimal:
    """Gross energy of a gas volume: SCM x kcal/SCM x kJ/kcal -> GJ."""
    return _pos("scm", scm) * _pos("gcv", gcv_kcal_per_scm) * _pos("kj_per_kcal", kj_per_kcal) / D(1_000_000)


def ncv_from_gcv(gj_gcv: Decimal, ratio: Decimal) -> Decimal:
    return _pos("gj_gcv", gj_gcv) * _pos("ncv_gcv_ratio", ratio)


def within(a: Decimal, b: Decimal, rel: Decimal) -> bool:
    """Relative closeness used by control checks and the two-reader comparison."""
    if a == b:
        return True
    denom = max(abs(a), abs(b))
    return denom != 0 and abs(a - b) / denom <= rel

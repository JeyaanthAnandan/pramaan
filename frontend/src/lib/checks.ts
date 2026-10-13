// Control checks are computed once and stored in English; the report shows them in the reader's
// language by their stable ids and phrases. Numbers, units and names stay as computed; anything not
// recognised is shown as stored.
import type { TFunction } from "i18next";

interface CheckLike { id: string; name: string; formula: string; result: string; tolerance: string; note?: string | null }

const KIND: Record<string, string> = {
  mass_balance: "mass",
  mass_balance_monthly: "mass_monthly",
  stock: "stock",
  exports: "exports",
  export_cn: "export_cn",
  supplier: "supplier",
  "gas.internal": "gas_internal",
  "gas.coverage": "gas_coverage",
  "gas.sec": "gas_sec",
  "electricity.excluded": "electricity",
};
const FORMULA: Record<string, string> = {
  "rod consumed − scrap ≈ product produced": "f_mass",
  "per month: rod − scrap ≈ produced": "f_mass_monthly",
  "purchases + opening stock − closing stock ≈ consumed": "f_stock",
  "purchases + opening − closing ≈ consumed": "f_stock",
  "Σ exported (t) ≤ Σ produced (t)": "f_exports",
  "CN on export invoices = CN of the process": "f_export_cn",
  "verification report present; statement period covers production months": "f_supplier_full",
  "verification report present": "f_supplier",
  "SCM × GCV(kcal/SCM) × 4.1868 kJ/kcal ÷ 1.055056 GJ/MMBtu ≈ MMBtu": "f_gas_internal",
  "months with an invoice / months in period": "f_gas_coverage",
  "GJ(NCV) ÷ t produced": "f_gas_sec",
  "iron & steel: direct emissions only (CBAM Reg. Annex II)": "f_electricity",
};
const EXACT: Record<string, string> = {
  verified: "r_verified",
  "no verified supplier data": "r_no_supplier",
  "insufficient data": "r_insufficient",
  exact: "t_exact",
  "all months": "t_all_months",
  "1 – 8 GJ/t (screws & nuts reference: 3.5 GJ/t, Guidance 5d Table 4-12)": "t_gas_sec",
  "Default value with mark-up is used for this precursor (Precursor Lever).": "n_default",
  "Upload all rod invoices and the stock lines of the register.": "n_upload_rod",
};
const PATTERNS: [RegExp, string][] = [
  [/^(\d+)\/(\d+) months within tolerance$/, "r_months_ok"],
  [/^(\d+)\/(\d+) invoices consistent$/, "r_invoices"],
  [/^(\d+)\/(\d+) months$/, "r_months"],
  [/^([\d.]+) kWh recorded$/, "r_kwh"],
  [/^(±[\d.]+ %) per month$/, "t_per_month"],
  [/^Missing months: (.+)$/, "n_missing_months"],
  [/^Missing: (.+)$/, "n_missing"],
];

function phrase(s: string | null | undefined, t: TFunction): string {
  if (!s) return s ?? "";
  if (EXACT[s]) return t(`checks.${EXACT[s]}`);
  for (const [rx, key] of PATTERNS) {
    const m = s.match(rx);
    if (m) return t(`checks.${key}`, { a: m[1], b: m[2], n: m[1], v: m[1], list: m[1] });
  }
  return s;
}

export function localizeCheck<C extends CheckLike>(c: C, t: TFunction): C {
  const kind = c.id.startsWith("gas.") || c.id.startsWith("electricity.") ? c.id : c.id.split(".")[0];
  const k = KIND[kind];
  const cut = c.name.indexOf(" — ");
  const line = cut >= 0 ? c.name.slice(cut + 3) : "";
  return {
    ...c,
    name: k ? t(`checks.name_${k}`, { line }) : c.name,
    formula: FORMULA[c.formula] ? t(`checks.${FORMULA[c.formula]}`) : c.formula,
    result: phrase(c.result, t),
    tolerance: phrase(c.tolerance, t),
    note: c.note ? phrase(c.note, t) : c.note,
  };
}

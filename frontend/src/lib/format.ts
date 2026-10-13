// Number formatting: tabular, units always shown, € and ₹ side by side (Indian grouping for ₹).

const locales: Record<string, string> = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", vi: "vi-VN" };

export function n(v: string | number | null | undefined, digits = 3, lang = "en"): string {
  if (v === null || v === undefined || v === "") return "—";
  const x = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(x)) return String(v);
  return x.toLocaleString(locales[lang] || "en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function eur(v: string | number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || v === "") return "—";
  const x = Number(v);
  return "€" + x.toLocaleString("en-IE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function inr(v: string | number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || v === "") return "—";
  const x = Number(v);
  return "₹" + x.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function compact(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e7) return (v / 1e7).toFixed(2) + " Cr";
  if (a >= 1e5) return (v / 1e5).toFixed(1) + " L";
  if (a >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(0);
}

export function inrCompact(v: string | number): string {
  return "₹" + compact(Number(v));
}

export function eurCompact(v: string | number): string {
  const x = Number(v);
  const a = Math.abs(x);
  if (a >= 1e6) return "€" + (x / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return "€" + (x / 1e3).toFixed(0) + "K";
  return "€" + x.toFixed(0);
}

export function pct(v: string | number, digits = 0): string {
  return Number(v).toFixed(digits) + "%";
}

export function ms(v: number | null | undefined): string {
  if (v === null || v === undefined) return "";
  return v < 1000 ? `${v} ms` : `${(v / 1000).toFixed(1)} s`;
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function cnFmt(cn: string): string {
  const d = cn.replace(/\D/g, "");
  return [d.slice(0, 4), ...(d.slice(4).match(/.{1,2}/g) || [])].join(" ");
}

/** "Jan–Sep 2026 (provisional, year-to-date)" in the reader's language, from the project's months.
 *  English keeps the server's own label. */
export function periodLabel(months: string[] | undefined, serverLabel: string, lang: string, ytd: string): string {
  if (lang === "en" || !months?.length) return serverLabel;
  const loc = locales[lang] || lang;
  const mon = (m: string) => new Date(`${m}-15T00:00:00`).toLocaleDateString(loc, { month: "short" });
  const year = months[months.length - 1].slice(0, 4);
  const span = months.length > 1 ? `${mon(months[0])}–${mon(months[months.length - 1])}` : mon(months[0]);
  return `${span} ${year}${/provisional/i.test(serverLabel) ? ` (${ytd})` : ""}`;
}

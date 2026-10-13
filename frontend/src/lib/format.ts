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

/** A quantity as a person types it on a phone, as the plain decimal the API stores, or null when it is not
 *  a usable number. Grouping commas go ("1,234.5", Indian "1,23,456"); a lone decimal comma counts as a
 *  point ("15,4" is 15.4, never 154); a unit or currency sign around it is ignored ("15.4 t", "₹ 21,192").
 *  In Vietnamese the dot groups and the comma is the decimal ("1.234,5"). */
export function parseQuantity(input: string, lang = "en"): string | null {
  if (/^\s*[-\u2212\u2013]/.test(input)) return null; // a minus sign: no bill, register or rate here is below zero
  let s = input.replace(/[\s\u00a0\u202f]/g, "").replace(/^[^\d]+|[^\d]+$/g, "");
  if (lang === "vi" && /^\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) s = s.replace(/\./g, "").replace(",", ".");
  else if (/^\d{1,3}(,\d{2,3})+(\.\d+)?$/.test(s) && /,\d{3}(\.\d+)?$/.test(s)) s = s.replace(/,/g, "");
  else if (/^\d+,\d+$/.test(s)) s = s.replace(",", ".");
  return /^\d+(\.\d+)?$/.test(s) ? s : null;
}

/** A date and time nobody can misread ("14 Oct 2026, 02:10 am"), in the reader's language. */
export function dateTime(iso: string, lang = "en"): string {
  return new Date(iso).toLocaleString(locales[lang] || "en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

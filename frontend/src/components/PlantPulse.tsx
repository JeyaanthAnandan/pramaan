import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { Activity, Flame, Leaf, TrendingDown } from "lucide-react";
import type { GasPulse } from "@/lib/api";
import { inr, n } from "@/lib/format";
import { EASE } from "@/lib/motion";
import { LensNum, useLens } from "./EvidenceLens";

const MONTH = (m: string, lang: string) => new Date(`${m}-15`).toLocaleDateString(lang === "en" ? "en-IN" : lang, { month: "short" });

/** Plant pulse: gas per tonne, month by month, against the plant's own median month. Hot months are
 *  marked with their excess in rupees (at the bill's own rate), energy and CO2; every bar and number
 *  opens the Evidence Lens down to the gas bill. Operations insight from the same verified data. */
export function PlantPulse({ pulse }: { pulse: GasPulse }) {
  const { t, i18n } = useTranslation();
  const { open } = useLens();
  const [hover, setHover] = useState<string | null>(null);
  const vals = pulse.months.map((m) => Number(m.gj_per_t));
  const med = Number(pulse.median);
  const top = Math.max(...vals, med) * 1.15; // bars start at zero: the dashed median line and the labels show the difference
  const h = (v: number) => (v / top) * 100;
  const hot = pulse.months.filter((m) => m.hot);
  const worst = hot.sort((a, b) => Number(b.delta_pct) - Number(a.delta_pct))[0];
  const lang = i18n.language;
  const shown = pulse.months.find((m) => m.month === hover) ?? worst ?? null;
  return (
    <section className="card overflow-hidden" aria-labelledby="pulse-title">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
        <Activity className="h-5 w-5 text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="eyebrow">{t("pulse.eyebrow")}</div>
          <h3 id="pulse-title" className="font-semibold">{t("pulse.title")}</h3>
        </div>
        <span className="w-full text-[12px] text-muted sm:w-auto">
          {t("pulse.median")} <LensNum node={pulse.median_node} className="font-mono font-semibold text-ink">{n(pulse.median, 2)}</LensNum> GJ/t
        </span>
      </div>
      <div className="grid gap-5 p-4 sm:p-5 lg:grid-cols-[1.35fr_1fr]">
        {/* the chart: one bar a month; the dashed line is the plant's own median month */}
        <figure aria-label={t("pulse.chart_label")}>
          <div className="relative h-52 pl-1">
            <div className="absolute inset-x-0 border-t-2 border-dashed border-ink/30" style={{ bottom: `${h(med)}%` }} aria-hidden>
              <span className="absolute -top-5 right-0 rounded bg-page px-1 font-mono text-[10px] text-muted">{t("pulse.median_short")} {n(pulse.median, 2)}</span>
            </div>
            <div className="relative flex h-full items-end gap-1 sm:gap-1.5">
              {pulse.months.map((m, i) => {
                const v = Number(m.gj_per_t);
                const d = Number(m.delta_pct);
                const isBest = m.month === pulse.best.month;
                const label = `${MONTH(m.month, lang)}: ${n(v, 2)} GJ/t, ${d >= 0 ? "+" : ""}${n(d, 1)} % ${t("pulse.vs_median")}${m.hot ? `, ${t("pulse.hot")}` : ""}${isBest ? `, ${t("pulse.best")}` : ""}`;
                return (
                  <button
                    key={m.month}
                    type="button"
                    className="group relative flex h-full flex-1 flex-col justify-end rounded-t-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                    onClick={() => open(m.node)}
                    onMouseEnter={() => setHover(m.month)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(m.month)}
                    onBlur={() => setHover(null)}
                    aria-label={label}
                  >
                    {m.hot && (
                      <motion.span className="mb-1 self-center whitespace-nowrap rounded bg-warnbg px-1 font-mono text-[10px] font-semibold text-warnink" initial={{ opacity: 0, y: 6 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.5 + i * 0.05, duration: 0.3 }} aria-hidden>
                        +{n(d, 0)}%
                      </motion.span>
                    )}
                    <motion.span
                      className={`block w-full rounded-t-md transition-colors ${m.hot ? "bg-warn" : isBest ? "bg-good/80" : hover === m.month ? "bg-accent/70" : "bg-accent/40"}`}
                      initial={{ height: 0 }}
                      whileInView={{ height: `${h(v)}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.6, ease: EASE, delay: i * 0.05 }}
                      aria-hidden
                    />
                  </button>
                );
              })}
            </div>
          </div>
          <div className="mt-1.5 flex gap-1 pl-1 sm:gap-1.5" aria-hidden>
            {pulse.months.map((m) => (
              <span key={m.month} className={`flex-1 text-center text-[10px] ${m.hot ? "font-semibold text-warnink" : m.month === pulse.best.month ? "font-semibold text-goodink" : "text-muted"}`}>
                {MONTH(m.month, lang)}
              </span>
            ))}
          </div>
          {/* readout for the bar under the pointer or focus (a tooltip would leave the card on a phone) */}
          <div className="mt-2 h-5 text-[12px]" aria-hidden>
            <AnimatePresence mode="wait">
              {shown && (
                <motion.span key={shown.month} className="inline-flex items-center gap-1.5" initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
                  <b>{MONTH(shown.month, lang)}</b> <span className="font-mono text-ink">{n(shown.gj_per_t, 2)}</span> GJ/t ·
                  <span className={shown.hot ? "font-semibold text-warnink" : Number(shown.delta_pct) < 0 ? "text-goodink" : "text-ink2"}>
                    {Number(shown.delta_pct) >= 0 ? "+" : ""}
                    {n(shown.delta_pct, 1)} % {t("pulse.vs_median")}
                  </span>
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <figcaption className="mt-1 text-[11px] text-muted">{t("pulse.caption", { pct: n(pulse.threshold_pct, 0) })}</figcaption>
        </figure>

        <div className="flex flex-col gap-3">
          {worst ? (
            <motion.div className="rounded-xl border border-warn/40 bg-warnbg/60 p-4" initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, ease: EASE }}>
              <div className="flex items-center gap-1.5 text-[12px] font-semibold text-warnink">
                <Flame className="h-4 w-4" aria-hidden /> {t("pulse.hot_t", { month: MONTH(worst.month, lang), pct: n(worst.delta_pct, 0) })}
              </div>
              {pulse.excess_inr && (
                <div className="mt-2 font-display text-[30px] font-semibold leading-none tracking-tight">
                  <LensNum node={pulse.excess_inr_node}>{inr(pulse.excess_inr)}</LensNum>
                </div>
              )}
              <p className="mt-1.5 text-[13px] text-ink2">
                {t(pulse.excess_inr ? "pulse.hot_inr" : "pulse.hot_gj")}{" "}
                <LensNum node={pulse.excess_gj_node}>{n(pulse.excess_gj, 0)} GJ</LensNum> ·{" "}
                <LensNum node={pulse.excess_tco2_node}>{n(pulse.excess_tco2, 1)} t CO2</LensNum>
              </p>
              <p className="mt-2 text-[12px] text-muted">{t("pulse.hot_d")}</p>
            </motion.div>
          ) : (
            <div className="rounded-xl border border-good/30 bg-goodbg/50 p-4 text-[13px] text-goodink">
              <Leaf className="mb-1 h-4 w-4" aria-hidden /> {t("pulse.none", { pct: n(pulse.threshold_pct, 0) })}
            </div>
          )}
          <div className="flex items-start gap-3 rounded-xl border border-line bg-sunk/60 p-4 text-[13px]">
            <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-goodink" aria-hidden />
            <p className="text-ink2">
              {t("pulse.best_t", { month: MONTH(pulse.best.month, lang) })} <LensNum node={pulse.best.node} className="font-mono font-semibold text-ink">{n(pulse.best.gj_per_t, 2)}</LensNum> GJ/t.{" "}
              {t("pulse.best_d")}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

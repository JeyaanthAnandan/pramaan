import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Clock, Gauge, ScanEye, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { AnimatedNumber, Reveal, rise, stagger } from "@/lib/motion";
import { LoadError } from "@/components/ErrorBoundary";

/** A rate shown as a percentage that counts up when first seen. */

/** A run's date and time in the reader's language: ten runs on one day differ only by the time. */
function runAt(iso: string | undefined, lang: string): string {
  return iso ? new Date(iso).toLocaleString(lang === "en" ? "en-IN" : lang, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
}

function Pct({ v }: { v?: number | null }) {
  if (v === undefined || v === null) return <>—</>;
  return <AnimatedNumber value={v * 100} format={(x) => `${x.toFixed(1)}%`} countUp />;
}

function Tile({ icon: Icon, label, value, target, ok, note }: { icon: typeof Gauge; label: string; value: ReactNode; target?: string; ok?: boolean | null; note?: string }) {
  const { t } = useTranslation();
  return (
    <motion.div variants={rise} className="card p-5">
      <div className="flex items-center gap-2 text-[13px] text-ink2">
        <Icon className="h-4 w-4 text-muted" /> {label}
      </div>
      <div className="num mt-2 font-display text-4xl font-semibold">{value}</div>
      {target && (
        <div className={`mt-1 text-[12px] ${ok === true ? "text-goodink" : ok === false ? "text-badink" : "text-muted"}`}>
          {t("metrics.target")}: {target} {ok === true ? "✓" : ok === false ? "✗" : ""}
        </div>
      )}
      {note && <div className="mt-1 text-[12px] text-muted">{note}</div>}
    </motion.div>
  );
}

export default function Metrics() {
  const { t, i18n } = useTranslation();
  const at = (iso?: string) => runAt(iso, i18n.language);
  const q = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  const m = q.data;
  const live = m?.runs?.live;
  const replay = m?.runs?.replay;
  const pct = (v?: number | null) => (v === undefined || v === null ? "—" : `${(v * 100).toFixed(1)}%`);
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <span className="chip">backend/eval/run_extraction_eval.py</span>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{t("metrics.title")}</h1>
      <p className="mt-2 max-w-2xl text-ink2">{t("metrics.lead")}</p>
      {q.isLoading && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-32" />
          ))}
        </div>
      )}
      {q.isError && <LoadError error={q.error} onRetry={() => void q.refetch()} />}
      {m && (
        <>
          {!live && (
            <p className="mt-6 rounded-2xl border border-warn/40 bg-warnbg px-4 py-3 text-[14px] text-warnink">
              {t((m.history as any[] | undefined)?.some((h) => h.mode === "live") ? "metrics.pending_history" : "metrics.pending")} {m.note ?? ""}
            </p>
          )}
          {live && (
            <section className="mt-8">
              <h2 className="eyebrow mb-3">Live · {live.models?.extraction} + {live.models?.second_reader} · {at(live.ran_at)}</h2>
              <motion.div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" variants={stagger(0.07)} initial="hidden" animate="show">
                <Tile icon={Gauge} label={t("metrics.field_acc")} value={<Pct v={live.field_accuracy} />} target="≥ 95%" ok={live.field_accuracy >= 0.95} note={`${live.fields_correct}/${live.fields_total} fields`} />
                <Tile icon={ScanEye} label={t("metrics.agreement")} value={<Pct v={live.two_reader_agreement} />} note={`box IoU ≥ 0.5: ${pct(live.box_hit_rate)}`} />
                <Tile icon={UserCheck} label={t("metrics.review_rate")} value={<Pct v={live.review_rate} />} />
                <Tile icon={Clock} label={t("metrics.total", { n: live.documents ?? 24 })} value={`${live.total_seconds?.toFixed?.(0) ?? "—"} s`} target="< 120 s" ok={live.total_seconds < 120} note={`${live.seconds_per_doc?.toFixed?.(1)} s / document`} />
              </motion.div>
            </section>
          )}
          {replay && (
            <section className="mt-8">
              <h2 className="eyebrow mb-3">Pipeline check · replay of ground truth (no model) · {at(replay.ran_at)}</h2>
              <motion.div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" variants={stagger(0.07)} initial="hidden" animate="show">
                <Tile icon={Gauge} label={t("metrics.field_acc")} value={<Pct v={replay.field_accuracy} />} note="sanity check of the eval harness, not a model score" />
                <Tile icon={ScanEye} label={t("metrics.agreement")} value={<Pct v={replay.two_reader_agreement} />} />
                <Tile icon={UserCheck} label={t("metrics.review_rate")} value={<Pct v={replay.review_rate} />} />
                <Tile icon={Clock} label={t("metrics.total", { n: replay.documents ?? 24 })} value={`${replay.total_seconds?.toFixed?.(1) ?? "—"} s`} />
              </motion.div>
            </section>
          )}
          {(live ?? replay)?.per_doc_type && (
            <Reveal className="mt-8 card overflow-hidden">
              <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={t("metrics.h_doctype")}>
              <table className="num w-full min-w-[520px] text-[13px]">
                <thead className="bg-sunk text-left text-[11px] text-muted">
                  <tr><th className="px-4 py-2">{t("metrics.h_doctype")}</th><th className="px-4 py-2 text-right">{t("metrics.h_fields")}</th><th className="px-4 py-2 text-right">{t("metrics.field_acc")}</th><th className="px-4 py-2 text-right">{t("metrics.agreement")}</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {Object.entries((live ?? replay).per_doc_type as Record<string, any>).map(([k, v]) => (
                    <tr key={k}><td className="px-4 py-2">{t(`doctype.${k}`, { defaultValue: k })}</td><td className="px-4 py-2 text-right">{v.fields}</td><td className="px-4 py-2 text-right">{pct(v.accuracy)}</td><td className="px-4 py-2 text-right">{pct(v.agreement)}</td></tr>
                  ))}
                </tbody>
              </table>
              </div>
            </Reveal>
          )}
          {m.history?.length > 0 && (
            <Reveal className="mt-8">
              <h2 className="eyebrow mb-3">{t("metrics.history_t")}</h2>
              <div className="card relative overflow-x-auto" tabIndex={0} role="region" aria-label={t("metrics.history_t")}>
                <table className="num w-full min-w-[640px] text-[13px]">
                  <thead className="bg-sunk text-left text-[11px] text-muted">
                    <tr>
                      <th className="px-4 py-2">{t("metrics.h_when")}</th>
                      <th className="px-4 py-2">{t("metrics.h_mode")}</th>
                      <th className="px-4 py-2 text-right">{t("metrics.field_acc")}</th>
                      <th className="px-4 py-2 text-right">{t("metrics.agreement")}</th>
                      <th className="px-4 py-2 text-right">{t("metrics.h_time")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {[...(m.history as any[])].reverse().map((h, i) => (
                      <tr key={`${h.ran_at}${i}`} className="align-top">
                        <td className="whitespace-nowrap px-4 py-2">{at(h.ran_at)}</td>
                        <td className="px-4 py-2">
                          <div className="font-medium">{h.mode === "live" ? t("metrics.mode_live") : t("metrics.mode_replay")}</div>
                          {h.note && <div className="mt-0.5 max-w-md text-[12px] leading-snug text-muted">{h.note}</div>}
                        </td>
                        <td className="px-4 py-2 text-right">{pct(h.field_accuracy)} <span className="text-[11px] text-muted">/ {h.fields_total}</span></td>
                        <td className="px-4 py-2 text-right">{pct(h.two_reader_agreement)}</td>
                        <td className="px-4 py-2 text-right">{h.total_seconds != null ? `${Number(h.total_seconds).toFixed(h.total_seconds < 10 ? 1 : 0)} s` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Reveal>
          )}
        </>
      )}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Clock, Gauge, Loader2, ScanEye, UserCheck } from "lucide-react";
import { api } from "@/lib/api";

function Tile({ icon: Icon, label, value, target, ok, note }: { icon: typeof Gauge; label: string; value: string; target?: string; ok?: boolean | null; note?: string }) {
  const { t } = useTranslation();
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 text-[13px] text-ink2">
        <Icon className="h-4 w-4 text-muted" /> {label}
      </div>
      <div className="mt-2 text-4xl font-semibold tracking-tight">{value}</div>
      {target && (
        <div className={`mt-1 text-[12px] ${ok === true ? "text-goodink" : ok === false ? "text-badink" : "text-muted"}`}>
          {t("metrics.target")}: {target} {ok === true ? "✓" : ok === false ? "✗" : ""}
        </div>
      )}
      {note && <div className="mt-1 text-[12px] text-muted">{note}</div>}
    </div>
  );
}

export default function Metrics() {
  const { t } = useTranslation();
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
      {q.isLoading && <Loader2 className="mt-10 h-6 w-6 animate-spin text-muted" />}
      {m && (
        <>
          {!live && <p className="mt-6 rounded-2xl border border-warn/40 bg-warnbg px-4 py-3 text-[14px] text-warnink">{t("metrics.pending")} {m.note ?? ""}</p>}
          {live && (
            <section className="mt-8">
              <h2 className="eyebrow mb-3">Live · {live.models?.extraction} + {live.models?.second_reader} · {live.ran_at}</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Tile icon={Gauge} label={t("metrics.field_acc")} value={pct(live.field_accuracy)} target="≥ 95%" ok={live.field_accuracy >= 0.95} note={`${live.fields_correct}/${live.fields_total} fields`} />
                <Tile icon={ScanEye} label={t("metrics.agreement")} value={pct(live.two_reader_agreement)} note={`box IoU ≥ 0.5: ${pct(live.box_hit_rate)}`} />
                <Tile icon={UserCheck} label={t("metrics.review_rate")} value={pct(live.review_rate)} />
                <Tile icon={Clock} label={t("metrics.total")} value={`${live.total_seconds?.toFixed?.(0) ?? "—"} s`} target="< 120 s" ok={live.total_seconds < 120} note={`${live.seconds_per_doc?.toFixed?.(1)} s / document`} />
              </div>
            </section>
          )}
          {replay && (
            <section className="mt-8">
              <h2 className="eyebrow mb-3">Pipeline check · replay of ground truth (no model) · {replay.ran_at}</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Tile icon={Gauge} label={t("metrics.field_acc")} value={pct(replay.field_accuracy)} note="sanity check of the eval harness, not a model score" />
                <Tile icon={ScanEye} label={t("metrics.agreement")} value={pct(replay.two_reader_agreement)} />
                <Tile icon={UserCheck} label={t("metrics.review_rate")} value={pct(replay.review_rate)} />
                <Tile icon={Clock} label={t("metrics.total")} value={`${replay.total_seconds?.toFixed?.(1) ?? "—"} s`} />
              </div>
            </section>
          )}
          {m.per_doc_type && (
            <section className="mt-8 card overflow-x-auto">
              <table className="num w-full min-w-[520px] text-[13px]">
                <thead className="bg-sunk text-left text-[11px] text-muted">
                  <tr><th className="px-4 py-2">Document type</th><th className="px-4 py-2 text-right">Fields</th><th className="px-4 py-2 text-right">Accuracy</th><th className="px-4 py-2 text-right">Agreement</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {Object.entries(m.per_doc_type as Record<string, any>).map(([k, v]) => (
                    <tr key={k}><td className="px-4 py-2">{t(`doctype.${k}`, { defaultValue: k })}</td><td className="px-4 py-2 text-right">{v.fields}</td><td className="px-4 py-2 text-right">{pct(v.accuracy)}</td><td className="px-4 py-2 text-right">{pct(v.agreement)}</td></tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}

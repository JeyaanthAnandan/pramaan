import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Lightbulb, Loader2, Table2, LineChart, Info } from "lucide-react";
import { api, type Result } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, inr, n } from "@/lib/format";
import { MoneyChart, type Series } from "./Charts";
import { LensNum } from "./EvidenceLens";

export function MoneySection({ result, whatIf, onWhatIf }: { result: Result; whatIf: boolean; onWhatIf: (v: boolean) => void }) {
  const { t } = useTranslation();
  const { pid, refresh, bundle } = useProject();
  const procs = result.processes.filter((p) => p.see);
  const [sel, setSel] = useState(procs[0]?.id ?? "P1");
  const [view, setView] = useState<"chart" | "table">("chart");
  const [fx, setFx] = useState(result.money.fx.value);
  const [price, setPrice] = useState(result.money.projection_price.value);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setFx(result.money.fx.value);
  }, [result.money.fx.value]);
  useEffect(() => {
    setPrice(result.money.projection_price.value);
  }, [result.money.projection_price.value]);

  const p = procs.find((x) => x.id === sel) ?? procs[0];
  const series = result.money.series[p.id];
  const wi = result.money.what_if[p.id];
  const s0 = series[0];
  const gap = Number(s0.gap_eur_t);
  const worse = gap < 0;
  const annual = gap * Number(p.exports_t) * (12 / 9);

  const chart: Series[] = useMemo(() => {
    const out: Series[] = [
      { key: "default", label: t("money.default"), color: "--s2", points: series.map((s) => ({ x: s.year, y: Number(s.default_eur_t), inr: Number(s.default_inr_t), node: s.nodes.default })) },
      { key: "actual", label: t("money.actual"), color: "--s1", points: series.map((s) => ({ x: s.year, y: Number(s.actual_eur_t), inr: Number(s.actual_inr_t), node: s.nodes.actual })) },
    ];
    if (wi && whatIf) out.push({ key: "whatif", label: t("money.whatif"), color: "--s3", dashed: true, points: wi.map((w) => ({ x: w.year, y: Number(w.eur_t), inr: Number(w.inr_t), node: w.node })) });
    return out;
  }, [series, wi, whatIf, t]);

  async function saveAssumptions() {
    setSaving(true);
    try {
      await api.patchProject(pid, { fx_inr_per_eur: fx, projection_price_eur: price });
      await refresh();
    } finally {
      setSaving(false);
    }
  }
  const dirty = fx !== result.money.fx.value || price !== result.money.projection_price.value;

  return (
    <section className="card p-4 sm:p-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{t("money.title")}</h2>
          <p className="mt-1 text-sm text-ink2">{t("money.lead")}</p>
        </div>
        <div className="flex rounded-xl border border-line bg-sunk p-1" role="tablist">
          {procs.map((x) => (
            <button key={x.id} role="tab" aria-selected={sel === x.id} onClick={() => setSel(x.id)} className={`min-h-[36px] rounded-lg px-3 text-[13px] font-medium transition ${sel === x.id ? "bg-surface text-ink shadow-card" : "text-ink2 hover:text-ink"}`}>
              CN {x.cn_display}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[260px_1fr]">
        <div className="space-y-4">
          <div>
            <div className="eyebrow">2026 · {p.name}</div>
            {!worse ? (
              <>
                <div className="num mt-1 font-display text-[44px] font-semibold leading-none">
                  <LensNum node={s0.nodes.gap}>{eur(gap)}</LensNum>
                </div>
                <div className="mt-1 text-lg font-semibold text-ink2">{inr(s0.gap_inr_t)}</div>
                <div className="text-sm text-muted">{t("money.gap")}</div>
                <div className="mt-3 rounded-xl border border-line bg-sunk px-3 py-2 text-[13px]">
                  ≈ <b className="num">{eur(annual)}</b> · <b className="num">{inr(annual * Number(result.money.fx.value))}</b> {t("money.per_year")}
                </div>
              </>
            ) : (
              <p className="mt-2 rounded-xl border border-warn/50 bg-warnbg px-3 py-2 text-[13px] leading-relaxed text-warnink">{t("money.worse")}</p>
            )}
          </div>
          <dl className="space-y-1.5 text-[13px]">
            <div className="flex justify-between gap-2">
              <dt className="flex items-center gap-1.5 text-ink2"><Sw c="--s1" />{t("money.actual")}</dt>
              <dd className="num font-semibold"><LensNum node={s0.nodes.actual}>{eur(s0.actual_eur_t)}</LensNum></dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="flex items-center gap-1.5 text-ink2"><Sw c="--s2" />{t("money.default")}</dt>
              <dd className="num font-semibold"><LensNum node={s0.nodes.default}>{eur(s0.default_eur_t)}</LensNum></dd>
            </div>
            {wi && (
              <div className="flex justify-between gap-2">
                <dt className="flex items-center gap-1.5 text-ink2"><Sw c="--s3" dashed />{t("money.whatif")}</dt>
                <dd className="num font-semibold"><LensNum node={wi[0].node}>{eur(wi[0].eur_t)}</LensNum></dd>
              </div>
            )}
          </dl>
          {wi && (
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2 text-[13px]">
              <input type="checkbox" checked={whatIf} onChange={(e) => onWhatIf(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--accent))]" />
              <span>{t("money.whatif")}</span>
            </label>
          )}
          <div className="space-y-2 rounded-xl border border-line bg-surface p-3 text-[13px]">
            <div className="flex items-center justify-between">
              <span className="eyebrow">{t("money.assumption")}</span>
              <Info className="h-3.5 w-3.5 text-muted" />
            </div>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">{t("money.fx")}</span>
              <input value={fx} onChange={(e) => setFx(e.target.value)} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            <div className="text-[11px] text-muted">ECB {result.money.fx.as_of ?? ""}</div>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">{t("money.price")}</span>
              <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            {dirty && (
              <button className="btn-primary h-9 min-h-0 w-full" onClick={saveAssumptions} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin" />} OK
              </button>
            )}
            {bundle?.project.is_demo && <div className="text-[11px] text-muted">2026: Q1 €75.36 · Q2 €75.28 · Q3 €82.32 (EC)</div>}
          </div>
        </div>

        <div>
          <div className="mb-2 flex justify-end">
            <div className="flex rounded-lg border border-line p-0.5">
              <button className={`inline-flex min-h-[32px] items-center gap-1 rounded-md px-2 text-[12px] ${view === "chart" ? "bg-sunk text-ink" : "text-muted"}`} onClick={() => setView("chart")}>
                <LineChart className="h-3.5 w-3.5" /> {t("money.chart")}
              </button>
              <button className={`inline-flex min-h-[32px] items-center gap-1 rounded-md px-2 text-[12px] ${view === "table" ? "bg-sunk text-ink" : "text-muted"}`} onClick={() => setView("table")}>
                <Table2 className="h-3.5 w-3.5" /> {t("money.table")}
              </button>
            </div>
          </div>
          {view === "chart" ? (
            <MoneyChart series={chart} gapBetween={["default", "actual"]} ariaLabel={`${t("money.title")} CN ${p.cn_display}`} />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="num w-full min-w-[560px] text-[13px]">
                <thead className="bg-sunk text-left text-[11px] text-muted">
                  <tr>
                    <th className="px-3 py-2">{t("money.year")}</th>
                    <th className="px-3 py-2 text-right">{t("money.actual")}</th>
                    <th className="px-3 py-2 text-right">{t("money.default")}</th>
                    {wi && <th className="px-3 py-2 text-right">{t("money.whatif")}</th>}
                    <th className="px-3 py-2 text-right">Δ €/t</th>
                    <th className="px-3 py-2 text-right">Δ ₹/t</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {series.map((s, i) => (
                    <tr key={s.year}>
                      <td className="px-3 py-1.5">{s.year}{s.price_status === "assumption" && <span className="text-muted">*</span>}</td>
                      <td className="px-3 py-1.5 text-right"><LensNum node={s.nodes.actual}>{eur(s.actual_eur_t)}</LensNum></td>
                      <td className="px-3 py-1.5 text-right"><LensNum node={s.nodes.default}>{eur(s.default_eur_t)}</LensNum></td>
                      {wi && <td className="px-3 py-1.5 text-right">{eur(wi[i].eur_t)}</td>}
                      <td className="px-3 py-1.5 text-right font-semibold">{eur(s.gap_eur_t)}</td>
                      <td className="px-3 py-1.5 text-right">{inr(s.gap_inr_t)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="px-3 py-2 text-[11px] text-muted">* {t("money.assumption")}: €{n(result.money.projection_price.value, 2)}</p>
            </div>
          )}
          <p className="mt-3 text-[12px] leading-relaxed text-muted">{t("money.formula")}</p>
        </div>
      </div>

      <div className="mt-5 flex gap-3 rounded-2xl border border-accent/20 bg-accent/5 p-4">
        <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
        <div>
          <div className="text-sm font-semibold">{t("money.myth_t")}</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink2">{t("money.myth")}</p>
        </div>
      </div>
    </section>
  );
}

function Sw({ c, dashed }: { c: string; dashed?: boolean }) {
  return (
    <svg width="14" height="6" aria-hidden>
      <line x1="0" x2="14" y1="3" y2="3" stroke={`rgb(var(${c}))`} strokeWidth="2" strokeDasharray={dashed ? "3 2" : undefined} />
    </svg>
  );
}

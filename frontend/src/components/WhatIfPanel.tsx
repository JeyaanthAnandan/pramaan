import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { Factory, FlameKindling, Loader2, Recycle, RotateCcw, Truck, Zap } from "lucide-react";
import type { Result } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, inr, n } from "@/lib/format";
import { AnimatedNumber, EASE, Segmented } from "@/lib/motion";
import { MoneyChart } from "./Charts";

interface SimPoint { year: number; eur_t: string; inr_t: string; now_eur_t: string; default_eur_t: string; buyer_now_eur_t: string; buyer_eur_t: string; buyer_inr_t: string; basis_now: "actual" | "default"; basis: "actual" | "default" }
interface Sim {
  see: string;
  see_now: string;
  direct: string;
  sefa: string;
  note: string;
  series: SimPoint[];
  plant: { rod_saved_t_per_year: string; gas_saved_gj_per_year: string | null; annual_factor: string };
  current: { scrap_pct: string | null; gas_gj_per_t: string | null; m: string };
  presets: Record<string, { rod_see: string; rod_sefa: string; source: string }>;
}

type Field = "rod" | "scrap" | "gas";
const EPS = 0.005;

/** X2: operations & decarbonisation levers - rod supplier data, yield (scrap) and heat treatment,
 *  computed by the same deterministic engine. Nothing is saved. */
export function WhatIfPanel({ result }: { result: Result }) {
  const { t } = useTranslation();
  const { pid } = useProject();
  const procs = result.processes.filter((p) => p.see);
  const ops = result.operations;
  const [proc, setProc] = useState(procs[procs.length - 1]?.id ?? "P1");
  const p = procs.find((x) => x.id === proc) ?? procs[0];
  const opsP = ops?.processes?.[p?.id ?? ""];
  const [rodSee, setRodSee] = useState("");
  const [rodSefa, setRodSefa] = useState("");
  const [scrap, setScrap] = useState("");
  const [gas, setGas] = useState("");
  const [heating, setHeating] = useState<"gas" | "electric">("gas");
  const [touched, setTouched] = useState<Set<Field>>(new Set());
  const [sim, setSim] = useState<Sim | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function reset() {
    if (!p) return;
    setRodSee(Number(p.precursor.see).toFixed(3));
    setRodSefa(Number(p.precursor.sefa).toFixed(3));
    setScrap(opsP ? Number(opsP.scrap_pct).toFixed(1) : "");
    setGas(ops?.gas_gj_per_t ? Number(ops.gas_gj_per_t).toFixed(2) : "");
    setHeating("gas");
    setTouched(new Set());
  }
  useEffect(() => {
    reset();
  }, [proc, result.computed_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const touch = (f: Field) => setTouched((s) => new Set(s).add(f));

  useEffect(() => {
    if (!p) return;
    const id = window.setTimeout(async () => {
      setBusy(true);
      setErr(null);
      try {
        const body: Record<string, string> = { process_id: proc, heating };
        if (touched.has("rod")) Object.assign(body, { rod_see: rodSee, rod_sefa: rodSefa });
        if (touched.has("scrap") && scrap !== "") body.scrap_pct = scrap;
        if (touched.has("gas") && gas !== "" && heating === "gas") body.gas_gj_per_t = gas;
        const r = await fetch(`/api/projects/${pid}/whatif`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const j = await r.json();
        if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : r.statusText);
        setSim(j);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => window.clearTimeout(id);
  }, [pid, proc, rodSee, rodSefa, scrap, gas, heating, touched, result.computed_at]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!p) return null;
  const s26 = sim?.series[0];
  const s30 = sim?.series.find((x) => x.year === 2030);
  const vsDefault = s26 ? Number(s26.default_eur_t) - Number(s26.eur_t) : 0;
  const rodSaved = sim ? Number(sim.plant.rod_saved_t_per_year) : 0;
  const gasSaved = sim?.plant.gas_saved_gj_per_year ? Number(sim.plant.gas_saved_gj_per_year) : 0;
  const basisLabel = (b?: "actual" | "default") => (b === "default" ? t("whatif.basis_default") : t("whatif.basis_actual"));
  return (
    <section className="card p-4 sm:p-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Factory className="h-5 w-5 text-s3" aria-hidden /> {t("whatif.title")}
          </h2>
          <p className="mt-1 text-sm text-ink2">{t("whatif.lead")}</p>
        </div>
        {procs.length > 1 && <Segmented value={proc} onChange={setProc} label={t("whatif.title")} options={procs.map((x) => ({ value: x.id, label: `CN ${x.cn_display}` }))} />}
      </div>
      <div className="mt-5 grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-3 text-[13px]">
          <fieldset className="space-y-2 rounded-xl border border-line p-3">
            <legend className="flex items-center gap-1.5 px-1 text-[12px] font-semibold">
              <Truck className="h-3.5 w-3.5 text-muted" aria-hidden /> {t("whatif.supplier", { precursor: p.precursor.name })}
            </legend>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">SEE (t CO2/t)</span>
              <input value={rodSee} onChange={(e) => { setRodSee(e.target.value); touch("rod"); }} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">SEFA (t CO2/t)</span>
              <input value={rodSefa} onChange={(e) => { setRodSefa(e.target.value); touch("rod"); }} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {sim &&
                Object.entries(sim.presets).map(([k, v]) => (
                  <button key={k} className="chip hover:border-accent/40" title={v.source} onClick={() => { setRodSee(v.rod_see); setRodSefa(v.rod_sefa); touch("rod"); }}>
                    {k.includes("stainless") ? "EC Ex. 2 (EAF)" : "EC Ex. 1 (BF-BOF)"}: {v.rod_see}
                  </button>
                ))}
            </div>
          </fieldset>
          {opsP && (
            <fieldset className="space-y-2 rounded-xl border border-line p-3">
              <legend className="flex items-center gap-1.5 px-1 text-[12px] font-semibold">
                <Recycle className="h-3.5 w-3.5 text-muted" aria-hidden /> {t("whatif.yield")}
              </legend>
              <label className="flex items-center justify-between gap-2">
                <span className="text-ink2">{t("whatif.scrap_pct")}</span>
                <input value={scrap} onChange={(e) => { setScrap(e.target.value); touch("scrap"); }} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
              </label>
              <input
                type="range"
                min={0}
                max={40}
                step={0.5}
                value={Number(scrap) || 0}
                onChange={(e) => { setScrap(Number(e.target.value).toFixed(1)); touch("scrap"); }}
                className="w-full accent-[rgb(var(--accent))]"
                aria-label={t("whatif.scrap_pct")}
              />
              <p className="text-[11px] text-muted">{t("whatif.scrap_now", { v: n(opsP.scrap_pct, 1), y: n(opsP.yield_pct, 1) })}</p>
            </fieldset>
          )}
          <fieldset className="space-y-2 rounded-xl border border-line p-3">
            <legend className="flex items-center gap-1.5 px-1 text-[12px] font-semibold">
              <FlameKindling className="h-3.5 w-3.5 text-muted" aria-hidden /> {t("whatif.heating")}
            </legend>
            <Segmented
              role="toggle"
              className="w-full"
              value={heating}
              onChange={setHeating}
              options={[
                { value: "gas", label: t("whatif.gas"), icon: <FlameKindling className="h-4 w-4" aria-hidden /> },
                { value: "electric", label: t("whatif.electric"), icon: <Zap className="h-4 w-4" aria-hidden /> },
              ]}
            />
            {heating === "gas" && ops?.gas_gj_per_t && (
              <>
                <label className="flex items-center justify-between gap-2">
                  <span className="text-ink2">{t("whatif.gas_gj")}</span>
                  <input value={gas} onChange={(e) => { setGas(e.target.value); touch("gas"); }} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
                </label>
                <p className="text-[11px] text-muted">{t("whatif.gas_now", { v: n(ops.gas_gj_per_t, 2) })}</p>
              </>
            )}
            {heating === "electric" && <p className="text-[12px] text-ink2">{sim?.note}</p>}
          </fieldset>
          <button className="link inline-flex items-center gap-1 text-[12px] disabled:no-underline disabled:opacity-50" onClick={reset} disabled={!touched.size && heating === "gas"}>
            <RotateCcw className="h-3 w-3" aria-hidden /> {t("whatif.reset")}
          </button>
        </div>
        <div className="min-w-0">
          {err && <p className="mb-3 rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
          <div className={`grid grid-cols-2 gap-3 transition-opacity ${busy ? "opacity-70" : ""}`} aria-live="polite">
            <Stat label="SEE (t CO2/t)" now={Number(p.see)} next={sim ? Number(sim.see) : null} fmt={(v) => n(v, 3)} />
            <Stat label={t("whatif.cost26")} now={s26 ? Number(s26.buyer_now_eur_t) : null} next={s26 ? Number(s26.buyer_eur_t) : null} fmt={(v) => eur(v)} sub={s26 ? `${inr(s26.buyer_inr_t)} · ${basisLabel(s26.basis)}` : ""} />
            <Stat label={t("whatif.cost30")} now={s30 ? Number(s30.buyer_now_eur_t) : null} next={s30 ? Number(s30.buyer_eur_t) : null} fmt={(v) => eur(v)} sub={s30 ? basisLabel(s30.basis) : ""} />
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("whatif.vsdefault")}</div>
              {s26 ? (
                vsDefault > EPS ? (
                  <div className="num mt-1 text-2xl font-semibold text-goodink">{t("whatif.saves", { v: eur(vsDefault) })}</div>
                ) : vsDefault < -EPS ? (
                  <div className="mt-1 text-[13px] font-semibold leading-snug text-warnink">{t("whatif.costs_more", { v: eur(-vsDefault) })}</div>
                ) : (
                  <div className="num mt-1 text-2xl font-semibold">{eur(0)}</div>
                )
              ) : (
                <div className="skeleton mt-2 h-7 w-24" />
              )}
              {s26 && <div className="text-[11px] text-muted">{t("whatif.default_is", { v: eur(s26.default_eur_t) })}</div>}
            </div>
          </div>
          <AnimatePresence initial={false}>
            {(rodSaved > EPS || gasSaved > EPS) && (
              <motion.div key="plant" className="grid grid-cols-2 gap-3 overflow-hidden" initial={{ height: 0, opacity: 0, marginTop: 0 }} animate={{ height: "auto", opacity: 1, marginTop: 12 }} exit={{ height: 0, opacity: 0, marginTop: 0 }} transition={{ duration: 0.3, ease: EASE }}>
                {rodSaved > EPS && <Plant label={t("whatif.rod_saved")} value={rodSaved} unit="t" />}
                {gasSaved > EPS && <Plant label={t("whatif.gas_saved")} value={gasSaved} unit="GJ" />}
              </motion.div>
            )}
          </AnimatePresence>
          {touched.has("scrap") && <p className="mt-3 text-[12px] leading-relaxed text-muted">{t("whatif.scrap_note")}</p>}
          {sim && (
            <div className="mt-4 rounded-xl border border-line p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <div className="text-[12px] font-semibold text-ink2">{t("whatif.chart_t")}</div>
                {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" aria-hidden />}
              </div>
              <MoneyChart
                compact
                height={210}
                ariaLabel={t("whatif.chart_t")}
                series={[
                  { key: "now", label: t("whatif.now"), color: "--s1", points: sim.series.map((x) => ({ x: x.year, y: Number(x.buyer_now_eur_t) })) },
                  ...(touched.size || heating === "electric"
                    ? [{ key: "next", label: t("whatif.with_changes"), color: "--s3", dashed: true, points: sim.series.map((x) => ({ x: x.year, y: Number(x.buyer_eur_t), inr: Number(x.buyer_inr_t) })) }]
                    : []),
                ]}
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/** Now -> with these changes. The new value tweens as you drag, so the eye follows what moved. */
function Stat({ label, now, next, fmt, sub }: { label: string; now: number | null; next: number | null; fmt: (v: number) => string; sub?: string }) {
  const delta = now !== null && next !== null ? next - now : 0;
  const changed = Math.abs(delta) > EPS;
  return (
    <div className="rounded-xl border border-line bg-surface p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
        <AnimatePresence initial={false}>
          {changed && now !== null && (
            <motion.span key="was" className="num text-sm text-muted line-through decoration-muted/50" initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
              {fmt(now)}
            </motion.span>
          )}
        </AnimatePresence>
        {next === null ? (
          <span className="skeleton inline-block h-7 w-20" />
        ) : (
          <AnimatedNumber value={next} format={fmt} className={`text-2xl font-semibold transition-colors duration-300 ${changed ? (delta < 0 ? "text-goodink" : "text-badink") : ""}`} />
        )}
      </div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function Plant({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="rounded-xl border border-good/30 bg-goodbg/60 p-3">
      <div className="text-[11px] text-goodink">{label}</div>
      <div className="mt-0.5 text-xl font-semibold text-goodink">
        <AnimatedNumber value={value} format={(v) => `${n(v, 0)} ${unit}`} />
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FlameKindling, Leaf, Loader2, Zap } from "lucide-react";
import type { Result } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, inr, n } from "@/lib/format";

interface Sim {
  see: string;
  see_now: string;
  direct: string;
  sefa: string;
  note: string;
  series: { year: number; eur_t: string; inr_t: string; now_eur_t: string; default_eur_t: string }[];
  presets: Record<string, { rod_see: string; rod_sefa: string; source: string }>;
}

/** X2: decarbonisation what-if — another rod supplier's verified data, electric heat treatment. */
export function WhatIfPanel({ result }: { result: Result }) {
  const { t } = useTranslation();
  const { pid } = useProject();
  const procs = result.processes.filter((p) => p.see);
  const [proc, setProc] = useState(procs[procs.length - 1]?.id ?? "P1");
  const p = procs.find((x) => x.id === proc)!;
  const [rodSee, setRodSee] = useState(p.precursor.see);
  const [rodSefa, setRodSefa] = useState(p.precursor.sefa);
  const [heating, setHeating] = useState<"gas" | "electric">("gas");
  const [sim, setSim] = useState<Sim | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setRodSee(Number(p.precursor.see).toFixed(3));
    setRodSefa(Number(p.precursor.sefa).toFixed(3));
    setHeating("gas");
  }, [proc]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const id = window.setTimeout(async () => {
      setBusy(true);
      setErr(null);
      try {
        const r = await fetch(`/api/projects/${pid}/whatif`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ process_id: proc, rod_see: rodSee, rod_sefa: rodSefa, heating }) });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail);
        setSim(j);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => window.clearTimeout(id);
  }, [pid, proc, rodSee, rodSefa, heating, result.computed_at]);

  const s26 = sim?.series[0];
  const s30 = sim?.series.find((x) => x.year === 2030);
  return (
    <section className="card p-4 sm:p-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Leaf className="h-5 w-5 text-s3" aria-hidden /> {t("whatif.title", { defaultValue: "Decarbonisation what-if" })}
          </h2>
          <p className="mt-1 text-sm text-ink2">{t("whatif.lead", { defaultValue: "Try another rod supplier's verified data or electric heat treatment. Computed by the same deterministic engine; nothing is saved." })}</p>
        </div>
        <div className="flex rounded-xl border border-line bg-sunk p-1" role="tablist">
          {procs.map((x) => (
            <button key={x.id} role="tab" aria-selected={proc === x.id} onClick={() => setProc(x.id)} className={`min-h-[36px] rounded-lg px-3 text-[13px] font-medium ${proc === x.id ? "bg-surface text-ink shadow-card" : "text-ink2"}`}>
              CN {x.cn_display}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-4 text-[13px]">
          <fieldset className="space-y-2 rounded-xl border border-line p-3">
            <legend className="px-1 text-[12px] font-semibold">{p.precursor.name}</legend>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">SEE (t CO2/t)</span>
              <input value={rodSee} onChange={(e) => setRodSee(e.target.value)} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            <label className="flex items-center justify-between gap-2">
              <span className="text-ink2">SEFA (t CO2/t)</span>
              <input value={rodSefa} onChange={(e) => setRodSefa(e.target.value)} inputMode="decimal" className="num w-24 rounded-lg border border-line2 bg-page px-2 py-1 text-right" />
            </label>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {sim &&
                Object.entries(sim.presets).map(([k, v]) => (
                  <button key={k} className="chip hover:border-accent/40" title={v.source} onClick={() => { setRodSee(v.rod_see); setRodSefa(v.rod_sefa); }}>
                    {k.includes("stainless") ? "EC Ex. 2 (EAF)" : "EC Ex. 1 (BF-BOF)"}: {v.rod_see}
                  </button>
                ))}
              <button className="chip" onClick={() => { setRodSee(Number(p.precursor.see).toFixed(3)); setRodSefa(Number(p.precursor.sefa).toFixed(3)); }}>
                {t("whatif.current", { defaultValue: "Current" })}
              </button>
            </div>
          </fieldset>
          <fieldset className="rounded-xl border border-line p-3">
            <legend className="px-1 text-[12px] font-semibold">{t("whatif.heating", { defaultValue: "Heat treatment" })}</legend>
            <div className="flex gap-2">
              {(["gas", "electric"] as const).map((h) => (
                <button key={h} onClick={() => setHeating(h)} className={`flex min-h-[40px] flex-1 items-center justify-center gap-1.5 rounded-lg border text-[13px] ${heating === h ? "border-ink bg-surface font-semibold" : "border-line text-ink2"}`} aria-pressed={heating === h}>
                  {h === "gas" ? <FlameKindling className="h-4 w-4" /> : <Zap className="h-4 w-4" />} {h === "gas" ? t("whatif.gas", { defaultValue: "Natural gas" }) : t("whatif.electric", { defaultValue: "Electric" })}
                </button>
              ))}
            </div>
            {heating === "electric" && <p className="mt-2 text-[12px] text-ink2">{sim?.note}</p>}
          </fieldset>
        </div>
        <div>
          {err && <p className="mb-3 rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
          <div className={`grid grid-cols-2 gap-3 transition ${busy ? "opacity-60" : ""}`}>
            <Stat label="SEE (t CO2/t)" now={n(p.see, 3)} next={sim ? n(sim.see, 3) : "…"} better={sim ? Number(sim.see) < Number(p.see) : null} />
            <Stat label={t("whatif.cost26", { defaultValue: "Buyer cost 2026 (€/t)" })} now={s26 ? eur(s26.now_eur_t) : "…"} next={s26 ? eur(s26.eur_t) : "…"} sub={s26 ? inr(s26.inr_t) : ""} better={s26 ? Number(s26.eur_t) < Number(s26.now_eur_t) : null} />
            <Stat label={t("whatif.cost30", { defaultValue: "Buyer cost 2030 (€/t)" })} now={s30 ? eur(s30.now_eur_t) : "…"} next={s30 ? eur(s30.eur_t) : "…"} better={s30 ? Number(s30.eur_t) < Number(s30.now_eur_t) : null} />
            <Stat label={t("whatif.vsdefault", { defaultValue: "Saved vs EU default, 2026 (€/t)" })} now="" next={s26 ? eur(Number(s26.default_eur_t) - Number(s26.eur_t)) : "…"} sub={s26 ? `${t("whatif.default_is", { defaultValue: "default" })} ${eur(s26.default_eur_t)}/t` : ""} better={s26 ? Number(s26.eur_t) < Number(s26.default_eur_t) : null} />
          </div>
          {busy && <Loader2 className="mt-2 h-4 w-4 animate-spin text-muted" />}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, now, next, sub, better }: { label: string; now: string; next: string; sub?: string; better: boolean | null }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
        {now && <span className="num text-sm text-muted line-through decoration-muted/50">{now}</span>}
        <span className={`num text-2xl font-semibold ${better === true ? "text-goodink" : better === false ? "text-badink" : ""}`}>{next}</span>
      </div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

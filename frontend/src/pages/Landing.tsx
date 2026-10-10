import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, Camera, FileCheck2, Factory, Globe2, Loader2, Play, ScanSearch, ScanEye, Scale, TrendingDown, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { rememberProject } from "@/lib/session";
import { StatusBadge } from "@/components/Status";

interface HeroDoc { doc: string; src: string; w: number; h: number; title: string; fields: { label: string; text: string; unit: string; box: number[]; alt?: string | null }[] }

function HeroLens() {
  const [docs, setDocs] = useState<HeroDoc[]>([]);
  const [i, setI] = useState(0);
  useEffect(() => {
    fetch("/hero/hero.json").then((r) => r.json()).then(setDocs).catch(() => setDocs([]));
  }, []);
  const steps = docs.flatMap((d) => d.fields.map((f) => ({ d, f })));
  useEffect(() => {
    if (!steps.length) return;
    const id = window.setInterval(() => setI((x) => (x + 1) % steps.length), 2600);
    return () => window.clearInterval(id);
  }, [steps.length]);
  if (!steps.length) return <div className="card aspect-[4/5] animate-pulse" />;
  const { d, f } = steps[i];
  const review = !!f.alt;
  return (
    <div className="relative">
      <div className="card relative overflow-hidden p-2 shadow-lift">
        <div className="relative overflow-hidden rounded-xl bg-sunk" style={{ aspectRatio: `${d.w} / ${d.h}` }}>
          {docs.map((x) => (
            <img key={x.doc} src={x.src} alt={x.title} className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-700 ${x.doc === d.doc ? "opacity-100" : "opacity-0"}`} />
          ))}
          <div
            className={`absolute rounded-[3px] border-2 transition-all duration-700 ease-[cubic-bezier(.2,.7,.2,1)] ${review ? "border-warn" : "border-good"} shadow-[0_0_0_9999px_rgb(0_0_0/0.22)]`}
            style={{ top: `${f.box[0] / 10}%`, left: `${f.box[1] / 10}%`, height: `${(f.box[2] - f.box[0]) / 10}%`, width: `${(f.box[3] - f.box[1]) / 10}%` }}
          />
        </div>
      </div>
      <div className="absolute -bottom-6 left-4 right-4 sm:-left-8 sm:right-auto sm:w-[300px]">
        <div key={i} className="card animate-rise p-4 shadow-lift">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow truncate">{f.label}</span>
            <StatusBadge status={review ? "NEEDS_REVIEW" : "VERIFIED_2R"} size="xs" />
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-semibold tracking-tight">{f.text}</span>
            <span className="text-sm text-muted">{f.unit}</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded-lg bg-sunk px-2 py-1">
              <div className="text-muted">Reader 1 · page</div>
              <div className="font-mono text-ink">{f.text}</div>
            </div>
            <div className={`rounded-lg px-2 py-1 ${review ? "bg-warnbg" : "bg-goodbg"}`}>
              <div className="text-ink2">Reader 2 · crop</div>
              <div className="font-mono text-ink">{f.alt ?? f.text}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const FACTS = [
  { k: "f1", href: "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en", src: "European Commission; EC Guidance No. 3, p. 115" },
  { k: "f2", href: "https://visionias.in/current-affairs/upsc-daily-news-summary/article/2026-01-29/business-standard/economy/india-eu-free-trade-agreement-cbam-rules-strain-indias-steel-msmes", src: "Business Standard via Vision IAS, 29 Jan 2026" },
  { k: "f3", href: "https://www.kotakneo.com/news/market-news/india-msme-compliance-costs-eu-carbon-border-adjustment-mechanism-2026/", src: "The Indian Express, reported 30 Jun 2026" },
  { k: "f4", href: "https://eurometal.net/cbam-efda-calls-for-immediate-corrections-to-avoid-jump-in-production-costs-of-eu-products-assembled-with-imported-fasteners/", src: "EFDA via Eurometal" },
];

export default function Landing() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [busy, setBusy] = useState<"load" | "live" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const golden = useQuery({ queryKey: ["golden"], queryFn: api.golden, staleTime: 60_000 });

  async function load(live: boolean) {
    setErr(null);
    setBusy(live ? "live" : "load");
    try {
      const r = await api.demoLoad(false);
      rememberProject(r.project_id);
      nav(live ? `/p/${r.project_id}/capture?autorun=1` : `/p/${r.project_id}/report`);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(null);
    }
  }

  async function startOwn() {
    setErr(null);
    try {
      const p = await api.createProject({ name: "My CBAM project", company: "My factory", country: "India" });
      rememberProject(p.id);
      nav(`/p/${p.id}/capture`);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  const nCases = golden.data?.cases?.length ?? 8;
  return (
    <div>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(60rem_30rem_at_80%_-10%,rgb(var(--accent)/0.10),transparent),radial-gradient(40rem_24rem_at_-10%_10%,rgb(var(--s3)/0.08),transparent)]" />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-10 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:pt-16">
          <div className="animate-rise">
            <span className="chip border-accent/25 bg-accent/5 text-accent">{t("landing.eyebrow")}</span>
            <h1 className="mt-5 text-[40px] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-6xl">{t("landing.title")}</h1>
            <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-ink2">{t("landing.lead")}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button className="btn-primary h-12 px-6 text-[15px]" onClick={() => load(false)} disabled={!!busy}>
                {busy === "load" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Factory className="h-4 w-4" />}
                {busy === "load" ? t("landing.loading") : t("landing.load")}
                <ArrowRight className="h-4 w-4" />
              </button>
              <button className="btn-ghost h-12 px-5" onClick={() => load(true)} disabled={!!busy} title={t("landing.live_hint")}>
                {busy === "live" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {t("landing.live")}
              </button>
            </div>
            <p className="mt-3 max-w-xl text-[13px] text-muted">{t("landing.sample_desc")}</p>
            <button className="link mt-2 text-[13px]" onClick={startOwn} disabled={!!busy}>
              {t("landing.own", { defaultValue: "Or start with your own documents →" })}
            </button>
            {err && <p className="mt-3 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
            <div className="mt-8 flex flex-wrap items-center gap-2">
              <Link to="/proof" className="inline-flex items-center gap-2 rounded-full border border-good/30 bg-goodbg px-3 py-1.5 text-[13px] font-semibold text-goodink transition hover:brightness-95">
                <BadgeCheck className="h-4 w-4" />
                {golden.data?.all_pass ? `${nCases}/${nCases}` : "…"} {t("landing.proof_strip")}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              {["Gemini 3.8 Flash", "Gemini 3.5 Flash-Lite", "ADK 2.x", "Cloud Run"].map((c) => (
                <span key={c} className="chip">{c}</span>
              ))}
            </div>
          </div>
          <div className="mx-auto w-full max-w-[460px] pb-8 lg:mx-0 lg:justify-self-end">
            <HeroLens />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 sm:px-6">
        <h2 className="eyebrow">{t("landing.steps_title")}</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            { icon: Camera, ti: "step1_t", d: "step1_d" },
            { icon: ScanSearch, ti: "step2_t", d: "step2_d" },
            { icon: FileCheck2, ti: "step3_t", d: "step3_d" },
          ].map((s, i) => (
            <div key={s.ti} className="card p-5">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-ink text-sm font-semibold text-page">{i + 1}</span>
                <s.icon className="h-5 w-5 text-muted" aria-hidden />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t(`landing.${s.ti}`)}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink2">{t(`landing.${s.d}`)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-14 max-w-7xl px-4 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            { icon: ScanSearch, k: "lens" },
            { icon: ScanEye, k: "2r" },
            { icon: Scale, k: "lever" },
            { icon: TrendingDown, k: "money" },
          ].map((u) => (
            <div key={u.k} className="card flex gap-4 p-5">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
                <u.icon className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <h3 className="font-semibold">{t(`landing.usp_${u.k}`)}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink2">{t(`landing.usp_${u.k}_d`)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-14 max-w-7xl px-4 sm:px-6">
        <h2 className="text-2xl font-semibold tracking-tight">{t("landing.why_title")}</h2>
        <ul className="mt-5 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
          {FACTS.map((f) => (
            <li key={f.k} className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-start sm:gap-6">
              <p className="flex-1 text-[15px] leading-relaxed">{t(`landing.${f.k}`)}</p>
              <a href={f.href} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-[12px] text-muted hover:text-accent sm:w-64 sm:justify-end">
                {t("landing.src")}: {f.src} <ExternalLink className="h-3 w-3" />
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-4 flex items-center gap-2 text-sm text-ink2">
          <Globe2 className="h-4 w-4 text-muted" /> {t("landing.jp")}
        </p>
      </section>
    </div>
  );
}

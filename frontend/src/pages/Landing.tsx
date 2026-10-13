import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, BadgeCheck, Calculator, Camera, Check, Compass, FileCheck2, Factory, FileSearch, Globe2, Loader2, Pause, Play, ScanEye, ScanSearch, Scale, Smartphone, Tags, TrendingDown, ExternalLink } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { lastProject, rememberPasscode, rememberProject } from "@/lib/session";
import { useToast } from "@/components/Toast";
import { EASE, Reveal, Stamp, rise, stagger, useAfter } from "@/lib/motion";

interface HeroDoc { doc: string; src: string; webp?: string; w: number; h: number; title: string; fields: { label: string; text: string; unit: string; box: number[]; alt?: string | null }[] }

/** The product in one loop: a value is boxed on the photo, reader 1 reads it from the page, reader 2
 *  reads only the crop, and the verdict is stamped (agree = verified; disagree = a person checks). */
function HeroLens() {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const [docs, setDocs] = useState<HeroDoc[]>([]);
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hold, setHold] = useState(false); // pointer or focus inside: stop advancing
  useEffect(() => {
    fetch("/hero/hero.json").then((r) => r.json()).then(setDocs).catch(() => setDocs([]));
  }, []);
  useEffect(() => {
    if (reduce) setPaused(true);
  }, [reduce]);
  const steps = docs.flatMap((d) => d.fields.map((f) => ({ d, f })));
  useEffect(() => {
    if (!steps.length || paused || hold) return;
    const id = window.setInterval(() => setI((x) => (x + 1) % steps.length), 3400);
    return () => window.clearInterval(id);
  }, [steps.length, paused, hold]);
  const second = useAfter(650, [i]);
  const verdict = useAfter(1250, [i]);
  if (!steps.length) return <div className="skeleton aspect-[4/5] rounded-2xl" />;
  const { d, f } = steps[i];
  const review = !!f.alt;
  return (
    <div className="relative" onMouseEnter={() => setHold(true)} onMouseLeave={() => setHold(false)} onFocus={() => setHold(true)} onBlur={() => setHold(false)}>
      <div className="card relative overflow-hidden p-2 shadow-lift">
        <div className="relative overflow-hidden rounded-xl bg-sunk" style={{ aspectRatio: `${d.w} / ${d.h}` }}>
          {docs.map((x, i) => (
            <picture key={x.doc}>
              {x.webp && <source srcSet={x.webp} type="image/webp" />}
              <img
                src={x.src}
                alt={x.title}
                width={879}
                height={1100}
                decoding="async"
                fetchPriority={i === 0 ? "high" : "low"}
                className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-700 ${x.doc === d.doc ? "opacity-100" : "opacity-0"}`}
              />
            </picture>
          ))}
          <div
            className={`absolute overflow-hidden rounded-[3px] border-2 transition-all duration-700 ease-[cubic-bezier(.2,.7,.2,1)] ${review && verdict ? "border-warn" : "border-good"} shadow-[0_0_0_9999px_rgb(0_0_0/0.22)]`}
            style={{ top: `${f.box[0] / 10}%`, left: `${f.box[1] / 10}%`, height: `${(f.box[2] - f.box[0]) / 10}%`, width: `${(f.box[3] - f.box[1]) / 10}%` }}
          >
            <span key={i} className="absolute inset-y-0 left-0 w-1/2 animate-scanx bg-gradient-to-r from-transparent via-white/70 to-transparent [animation-delay:500ms]" aria-hidden />
          </div>
          <div className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-full bg-surface/90 px-2 py-1 shadow-card backdrop-blur">
            <button type="button" onClick={() => setPaused((p) => !p)} className="grid h-6 w-6 place-items-center rounded-full text-ink2 hover:bg-sunk hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60" aria-label={paused ? t("landing.play") : t("landing.pause")}>
              {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            </button>
            {steps.map((_, j) => (
              <button key={j} type="button" onClick={() => setI(j)} className="group grid h-6 w-3.5 place-items-center" aria-label={`${j + 1} / ${steps.length}`} aria-current={j === i ? "step" : undefined}>
                <span className={`block h-1.5 rounded-full transition-all duration-300 ${j === i ? "w-3.5 bg-accent" : "w-1.5 bg-line2 group-hover:bg-muted"}`} />
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="absolute -bottom-6 left-4 right-4 sm:-left-8 sm:right-auto sm:w-[310px]">
        <motion.div key={i} className="card relative p-4 shadow-lift" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
          <div className="eyebrow truncate">{f.label}</div>
          {verdict && (
            <span className="absolute -right-3 -top-3">
              <Stamp tone={review ? "warn" : "good"} className="border-2 px-1.5 py-0.5 text-[10px] tracking-[0.08em] shadow-card">
                {review ? "≠" : <Check className="h-3 w-3" aria-hidden />} {review ? t("status.NEEDS_REVIEW") : t("status.VERIFIED_2R")}
              </Stamp>
            </span>
          )}
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-semibold tracking-tight">{f.text}</span>
            <span className="text-sm text-muted">{f.unit}</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded-lg bg-sunk px-2 py-1">
              <div className="text-muted">{t("gaps.reader1")}</div>
              <div className="font-mono text-ink">{f.text}</div>
            </div>
            <motion.div className={`rounded-lg px-2 py-1 transition-colors duration-500 ${verdict ? (review ? "bg-warnbg" : "bg-goodbg") : "bg-sunk"}`} initial={false} animate={second ? { opacity: 1, x: 0 } : { opacity: 0, x: -8 }} transition={{ duration: 0.3, ease: EASE }}>
              <div className="text-ink2">{t("gaps.reader2")}</div>
              <div className="font-mono text-ink">{f.alt ?? f.text}</div>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

const PIPE = [
  { k: "photo", icon: Smartphone, m: "PWA · camera" },
  { k: "class", icon: Tags, m: "gemini-3.8-flash" },
  { k: "r1", icon: FileSearch, m: "gemini-3.8-flash" },
  { k: "r2", icon: ScanEye, m: "gemini-3.5-flash-lite" },
  { k: "engine", icon: Calculator, m: "Decimal · EC refdata" },
  { k: "out", icon: FileCheck2, m: "PDF · Excel · pack" },
];

/** How one photo becomes a number a verifier can follow: a dot travels the stages in order. */
function Pipeline() {
  const { t } = useTranslation();
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="eyebrow">{t("landing.pipe_title")}</h2>
            <p className="mt-2 max-w-2xl text-[15px] text-ink2">{t("landing.pipe_lead")}</p>
          </div>
          <Link to="/try" className="btn-ghost nudge min-h-[40px] px-4 text-[13px]">
            <ScanEye className="h-4 w-4 text-accent" aria-hidden /> {t("try.pipe_cta")} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
      </Reveal>
      <Reveal delay={0.1} className="relative mt-5">
        <div className="pointer-events-none absolute left-[8.333%] right-[8.333%] top-[34px] z-[5] hidden h-px bg-line2 lg:block" aria-hidden>
          <span className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 animate-travel rounded-full bg-accent shadow-[0_0_0_4px_rgb(var(--accent)/0.18)]" />
        </div>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {PIPE.map((s, i) => (
            <li key={s.k} className="relative flex gap-3 rounded-2xl border border-line bg-surface p-3 shadow-card lg:flex-col lg:items-center lg:text-center">
              <span className="relative z-10 grid h-11 w-11 shrink-0 animate-pipeglow place-items-center rounded-xl border border-line bg-surface text-accent" style={{ animationDelay: `${i}s` }}>
                <s.icon className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold">
                  <span className="num mr-1 text-muted">{i + 1}</span>
                  {t(`landing.pipe_${s.k}`)}
                </div>
                <div className="mt-0.5 text-[12px] leading-snug text-ink2">{t(`landing.pipe_${s.k}_d`)}</div>
                <div className="mt-1 font-mono text-[10.5px] text-accent">{s.m}</div>
              </div>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
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
  const [busy, setBusy] = useState<"load" | "live" | "own" | "tour" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const golden = useQuery({ queryKey: ["golden"], queryFn: api.golden, staleTime: 60_000 });
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.metrics, staleTime: 300_000 });
  const toast = useToast();

  async function load(live: boolean, tour = false) {
    setErr(null);
    setBusy(tour ? "tour" : live ? "live" : "load");
    const where = (id: string) => (live ? `/p/${id}/capture?autorun=1` : `/p/${id}/report${tour ? "?tour=1" : ""}`);
    try {
      const r = await api.demoLoad(false);
      rememberProject(r.project_id);
      nav(where(r.project_id));
    } catch (e) {
      const prev = lastProject();
      if (e instanceof ApiError && e.status === 429 && prev?.startsWith("demo-")) {
        // too many fresh copies from this address: reopen this visitor's earlier copy instead
        toast(t("toast.reuse_sample"), "info");
        nav(where(prev));
      } else setErr(String((e as Error).message));
    } finally {
      setBusy(null);
    }
  }

  async function startOwn() {
    setErr(null);
    setBusy("own");
    try {
      const p = await api.createProject({ name: "My CBAM project", company: t("setup.my_factory"), country: "India" });
      rememberProject(p.id);
      rememberPasscode(p.id, p.access_key);
      nav(`/p/${p.id}/capture#setup`);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(null);
    }
  }

  const nCases = golden.data?.cases?.length ?? 8;
  const live = metrics.data?.runs?.live;
  return (
    <div>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(60rem_30rem_at_80%_-10%,rgb(var(--accent)/0.10),transparent),radial-gradient(40rem_24rem_at_-10%_10%,rgb(var(--s3)/0.08),transparent)]" />
        <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] items-center gap-12 px-4 pb-20 pt-10 sm:px-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:pt-16">
          <motion.div variants={stagger(0.08)} initial="hidden" animate="show" className="min-w-0">
            <motion.span variants={rise} className="chip border-accent/25 bg-accent/5 text-accent">
              {t("landing.eyebrow")}
            </motion.span>
            {/* the headline and lead are the page's first read and its largest paint: shown at once, not faded in */}
            <h1 className="mt-5 break-words text-[40px] font-semibold leading-[1.05] tracking-[-0.01em] sm:text-6xl">{t("landing.title")}</h1>
            <p className="mt-5 max-w-xl break-words text-[17px] leading-relaxed text-ink2">{t("landing.lead")}</p>
            <motion.div variants={rise} className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button className="btn-primary glint nudge min-h-12 px-6 py-2 text-[15px]" onClick={() => load(false)} disabled={!!busy}>
                {busy === "load" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Factory className="h-4 w-4" />}
                {busy === "load" ? t("landing.loading") : t("landing.load")}
                <ArrowRight className="h-4 w-4" />
              </button>
              <button className="btn-ghost min-h-12 px-5 py-2" onClick={() => load(false, true)} disabled={!!busy}>
                {busy === "tour" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Compass className="h-4 w-4 text-accent" />}
                {t("tour.landing")}
              </button>
              <button className="btn-quiet min-h-12 px-4 py-2" onClick={() => load(true)} disabled={!!busy} title={t("landing.live_hint")}>
                {busy === "live" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {t("landing.live")}
              </button>
            </motion.div>
            <motion.div variants={rise}>
              <p className="mt-3 max-w-xl text-[13px] text-muted">{t("landing.sample_desc")}</p>
              <button className="link mt-2 inline-flex items-center gap-1.5 text-[13px]" onClick={startOwn} disabled={!!busy}>
                {busy === "own" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {t("landing.own", { defaultValue: "Or start with your own documents →" })}
              </button>
              <Link to="/try" className="link mt-1 flex w-fit items-center gap-1.5 text-[13px]">
                {t("try.landing_link")}
              </Link>
              {err && <p className="mt-3 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
            </motion.div>
            <motion.div variants={rise} className="mt-8 flex flex-wrap items-center gap-x-3 gap-y-2">
              <Link to="/proof" className="nudge inline-flex items-center gap-2 rounded-full border border-good/30 bg-goodbg px-3 py-1.5 text-[13px] font-semibold text-goodink transition hover:brightness-95">
                <BadgeCheck className="h-4 w-4" />
                {golden.data?.all_pass ? `${nCases}/${nCases}` : "…"} {t("landing.proof_strip")}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              {live?.fields_total ? (
                // the latest live Gemini evaluation, only when one exists on this deployment
                <Link to="/metrics" className="nudge inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/5 px-3 py-1.5 text-[13px] font-semibold text-accent transition hover:brightness-95">
                  <ScanEye className="h-4 w-4" aria-hidden />
                  {t("landing.live_strip", { ok: live.fields_correct, n: live.fields_total, s: Math.round(live.total_seconds) })}
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              ) : null}
              <span className="flex flex-wrap items-center gap-1.5 text-[12px] text-muted">
                {t("landing.built")}:
                {["Gemini 3.8 Flash", "Gemini 3.5 Flash-Lite", "Gemini 3.8 Live", "ADK 2.x", "Cloud Run"].map((c) => (
                  <span key={c} className="chip">{c}</span>
                ))}
              </span>
            </motion.div>
          </motion.div>
          <motion.div className="mx-auto w-full max-w-[460px] pb-8 lg:mx-0 lg:justify-self-end" initial={{ opacity: 0, y: 16, rotate: 0.6 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ duration: 0.6, ease: EASE, delay: 0.2 }}>
            <HeroLens />
          </motion.div>
        </div>
      </section>

      <Pipeline />

      <section className="mx-auto mt-14 max-w-7xl px-4 sm:px-6">
        <Reveal>
          <h2 className="eyebrow">{t("landing.steps_title")}</h2>
        </Reveal>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            { icon: Camera, ti: "step1_t", d: "step1_d" },
            { icon: ScanSearch, ti: "step2_t", d: "step2_d" },
            { icon: FileCheck2, ti: "step3_t", d: "step3_d" },
          ].map((s, i) => (
            <Reveal key={s.ti} delay={i * 0.08} className="card card-hover p-5">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-ink text-sm font-semibold text-page">{i + 1}</span>
                <s.icon className="h-5 w-5 text-muted" aria-hidden />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t(`landing.${s.ti}`)}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink2">{t(`landing.${s.d}`)}</p>
            </Reveal>
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
          ].map((u, i) => (
            <Reveal key={u.k} delay={(i % 2) * 0.08} className="card card-hover flex gap-4 p-5">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
                <u.icon className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <h3 className="font-semibold">{t(`landing.usp_${u.k}`)}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink2">{t(`landing.usp_${u.k}_d`)}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-14 max-w-7xl px-4 sm:px-6">
        <Reveal>
          <h2 className="text-2xl font-semibold tracking-tight">{t("landing.why_title")}</h2>
        </Reveal>
        <Reveal delay={0.05}>
          <ul className="mt-5 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
            {FACTS.map((f) => (
              <li key={f.k} className="flex flex-col gap-1 px-5 py-4 transition-colors hover:bg-sunk/40 sm:flex-row sm:items-start sm:gap-6">
                <p className="flex-1 text-[15px] leading-relaxed">{t(`landing.${f.k}`)}</p>
                <a href={f.href} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-[12px] text-muted hover:text-accent sm:w-64 sm:justify-end">
                  {t("landing.src")}: {f.src} <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            ))}
          </ul>
        </Reveal>
        <p className="mt-4 flex items-center gap-2 text-sm text-ink2">
          <Globe2 className="h-4 w-4 text-muted" /> {t("landing.jp")}
        </p>
      </section>
    </div>
  );
}

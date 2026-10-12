import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { BadgeCheck, BookOpenCheck, Check, ChevronDown, ClipboardCheck, Copy, ExternalLink, FileArchive, FileSpreadsheet, FileText, Link2, Loader2, MousePointerClick, ShieldAlert, ShieldCheck, Sparkles } from "lucide-react";
import { api, exportUrl, type ProcessResult } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, inr, n } from "@/lib/format";
import { AnimatedNumber, Collapse, SPRING, rise, stagger, useRise } from "@/lib/motion";
import { LensNum } from "@/components/EvidenceLens";
import { ContributionBar, CostBars, ReadinessRing } from "@/components/Charts";
import { StatusBadge } from "@/components/Status";
import { MoneySection } from "@/components/MoneySection";
import { Lever } from "@/components/Lever";
import { WhatIfPanel } from "@/components/WhatIfPanel";
import { NextSteps } from "@/components/NextSteps";
import { useToast } from "@/components/Toast";
import { NoResult } from "./Gaps";

const SECTIONS = ["next", "lines", "money", "levers", "share", "checks"] as const;

export default function Report() {
  const { result } = useProject();
  const [whatIf, setWhatIf] = useState(false);
  if (!result) return <NoResult />;
  const procs = result.processes.filter((p) => p.see);
  return (
    <div className="space-y-6">
      <Verdict />
      <SectionNav />

      <div id="next">
        <NextSteps />
      </div>

      <motion.div id="lines" className="grid gap-5 lg:grid-cols-2" variants={stagger(0.08, 0.1)} initial="hidden" animate="show">
        {procs.map((p) => (
          <ProcessCard key={p.id} p={p} />
        ))}
      </motion.div>

      <div className="space-y-4">
        {[...procs]
          .sort((a, b) => Number(a.precursor.data === "ACTUAL_VERIFIED") - Number(b.precursor.data === "ACTUAL_VERIFIED"))
          .map((p) => (
            <Lever key={p.id} p={p} result={result} whatIf={whatIf} onWhatIf={setWhatIf} />
          ))}
      </div>

      <div id="money">
        <MoneySection result={result} whatIf={whatIf} onWhatIf={setWhatIf} />
      </div>

      <div id="levers">
        <WhatIfPanel result={result} />
      </div>

      <div id="share" className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Explanations />
        <Exports />
      </div>
      <div id="checks">
        <Checks />
      </div>
    </div>
  );
}

/** The answer first: what the exporter's data is worth to the buyer, what more is within reach,
 *  and how much is ready to declare. Every figure is the engine's; nothing is computed here. */
function Verdict() {
  const { t } = useTranslation();
  const { result } = useProject();
  const r = result!;
  const fx = Number(r.money.fx.value);
  const rd = r.readiness;
  const procs = r.processes.filter((p) => p.see);
  const secured = procs.filter((p) => p.buyer.basis_2026 === "actual" && Number(p.buyer.gap_vs_default_eur_t) > 0);
  const securedAnnual = secured.reduce((a, p) => a + Number(p.buyer.annual_gap_eur), 0);
  const reach = procs.filter((p) => p.precursor.data !== "ACTUAL_VERIFIED" && Number(p.buyer.supplier_saving_annual_eur ?? 0) > 0);
  const reachAnnual = reach.reduce((a, p) => a + Number(p.buyer.supplier_saving_annual_eur ?? 0), 0);
  const allReady = rd.lines_total > 0 && rd.lines_ready === rd.lines_total;
  const cols = 1 + Number(securedAnnual > 0) + Number(reachAnnual > 0);
  const rose = useRise(securedAnnual); // a supplier's verified data just landed: show what it added
  return (
    <section className="card overflow-hidden" aria-labelledby="verdict-title">
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="min-w-0">
            <div className="eyebrow">{r.period_label}</div>
            <h2 id="verdict-title" className="mt-1 text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">
              {t("report.title")}
            </h2>
          </div>
          <p className="flex items-center gap-1.5 text-[12px] text-muted">
            <MousePointerClick className="h-3.5 w-3.5" aria-hidden /> {t("report.click_hint")}
          </p>
        </div>
        <motion.div className={`mt-5 grid gap-3 ${cols === 3 ? "md:grid-cols-3" : cols === 2 ? "md:grid-cols-2" : ""}`} variants={stagger(0.09)} initial="hidden" animate="show">
          {securedAnnual > 0 && (
            <motion.div variants={rise} className="flex flex-col rounded-xl border border-good/30 bg-goodbg/50 p-4">
              <div className="flex items-center gap-1.5 text-[12px] font-semibold text-goodink">
                <ShieldCheck className="h-4 w-4" aria-hidden /> {t("verdict.secured_t")}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 font-display text-[36px] font-semibold leading-none tracking-tight">
                <AnimatedNumber value={securedAnnual} format={(v) => eur(v)} countUp />
                <AnimatePresence>
                  {rose && (
                    <motion.span
                      key="rise"
                      className="rounded-full bg-good px-2.5 py-1 font-sans text-[13px] font-semibold tracking-normal text-white"
                      initial={{ opacity: 0, y: 10, scale: 0.6 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ type: "spring", stiffness: 520, damping: 22 }}
                      role="status"
                    >
                      +{eur(rose)}
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>
              <div className="mt-1.5 text-[13px] text-ink2">
                <AnimatedNumber value={securedAnnual * fx} format={(v) => inr(v)} countUp /> · {t("verdict.per_year")}
              </div>
              <div className="mt-auto pt-3 text-[12px] leading-snug text-muted">
                {secured.length === 1 ? t("verdict.secured_one", { saving: eur(secured[0].buyer.gap_vs_default_eur_t), product: secured[0].name }) : t("verdict.secured_many", { count: secured.length })}
              </div>
            </motion.div>
          )}
          {reachAnnual > 0 && (
            <motion.div variants={rise} className="flex flex-col rounded-xl border border-accent/25 bg-accent/5 p-4">
              <div className="flex items-center gap-1.5 text-[12px] font-semibold text-accent">
                <Sparkles className="h-4 w-4" aria-hidden /> {t("verdict.reach_t")}
              </div>
              <div className="mt-2 font-display text-[36px] font-semibold leading-none tracking-tight">
                +<AnimatedNumber value={reachAnnual} format={(v) => eur(v)} countUp />
              </div>
              <div className="mt-1.5 text-[13px] text-ink2">
                +<AnimatedNumber value={reachAnnual * fx} format={(v) => inr(v)} countUp /> · {t("verdict.per_year")}
              </div>
              <div className="mt-auto pt-3 text-[12px] leading-snug text-muted">
                {reach.length === 1 ? (
                  <a href={`#lever-${reach[0].id}`} className="hover:text-accent">
                    {t("verdict.reach_one", { supplier: reach[0].precursor.supplier, saving: eur(reach[0].buyer.supplier_saving_eur_t), product: reach[0].name })} →
                  </a>
                ) : (
                  t("verdict.reach_many")
                )}
              </div>
            </motion.div>
          )}
          <motion.div variants={rise} className="flex items-center gap-4 rounded-xl border border-line bg-sunk/50 p-4">
            <ReadinessRing value={Number(rd.score)} size={78} stroke={7} label={t("report.readiness")} />
            <div className="min-w-0">
              <div className="text-[12px] font-semibold text-ink2">{t("verdict.ready_t")}</div>
              {rd.lines_total > 0 && (
                <div className={`mt-1 text-[14px] font-semibold leading-snug ${allReady ? "text-goodink" : "text-warnink"}`}>{t("report.lines_ready", { ready: rd.lines_ready, total: rd.lines_total })}</div>
              )}
              <div className="mt-1 text-[12px] leading-snug text-muted">
                <b className="num text-ink2">{Number(rd.score).toFixed(0)}%</b> {t("report.readiness_d")}
              </div>
              {procs.length > 1 && (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {procs.map((p) => {
                    const ok = rd.by_process?.[p.id]?.ready;
                    return (
                      <li key={p.id} className={`chip ${ok ? "border-good/30 bg-goodbg text-goodink" : "border-warn/40 bg-warnbg text-warnink"}`}>
                        {ok ? <Check className="h-3 w-3" aria-hidden /> : <span aria-hidden>!</span>} CN {p.cn_display}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </motion.div>
        </motion.div>
      </div>
      <div className="flex items-start gap-2 border-t border-warn/30 bg-warnbg/70 px-5 py-2.5 text-[12px] leading-relaxed text-warnink sm:px-6">
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span>
          <b>{t("app.provisional")}</b> {t("app.disclaimer")}
        </span>
      </div>
    </section>
  );
}

/** Sticky "on this page" bar; the highlight follows the section in view. */
function SectionNav() {
  const { t } = useTranslation();
  const [active, setActive] = useState<string>(SECTIONS[0]);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    // on a phone the bar scrolls sideways: keep the current section's chip in view
    const ul = list.current;
    const a = ul?.querySelector<HTMLElement>(`a[href="#${active}"]`);
    if (ul && a && ul.scrollWidth > ul.clientWidth) ul.scrollTo({ left: a.offsetLeft - ul.clientWidth / 2 + a.offsetWidth / 2, behavior: "smooth" });
  }, [active]);
  useEffect(() => {
    let raf = 0;
    const pick = () => {
      raf = 0;
      let cur: string = SECTIONS[0];
      for (const s of SECTIONS) {
        const el = document.getElementById(s);
        if (el && el.getBoundingClientRect().top <= 150) cur = s;
      }
      const atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      setActive(atEnd ? SECTIONS[SECTIONS.length - 1] : cur);
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(pick);
    };
    pick();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);
  return (
    <nav aria-label={t("report.on_page")} className="sticky top-[67px] z-20 -mx-4 border-b border-line/70 bg-page/90 px-4 py-2 backdrop-blur-md sm:-mx-6 sm:px-6">
      <ul ref={list} className="no-scrollbar relative -mx-1 flex gap-1 overflow-x-auto px-1">
        {SECTIONS.map((s) => {
          const on = active === s;
          return (
            <li key={s} className="shrink-0">
              <a href={`#${s}`} aria-current={on ? "location" : undefined} className={`relative block whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors ${on ? "text-ink" : "text-ink2 hover:text-ink"}`}>
                {on && <motion.span layoutId="secnav" className="absolute inset-0 rounded-full border border-line2 bg-surface shadow-card" transition={SPRING} aria-hidden />}
                <span className="relative">{t(`report.nav_${s}`)}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function ProcessCard({ p }: { p: ProcessResult }) {
  const { t } = useTranslation();
  const { result, bundle } = useProject();
  const tree = result!.calc_tree;
  const fx = Number(result!.money.fx.value);
  const actual = p.precursor.data === "ACTUAL_VERIFIED";
  const contrib = Number(tree[`${p.id}.rod.contrib`]?.value ?? 0);
  const b = p.buyer;
  const onDefault = b.basis_2026 === "default";
  const rp = result!.readiness.by_process?.[p.id];
  return (
    <motion.article variants={rise} className="card min-w-0 p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="eyebrow">
            {t("report.cn_group")} · CN {p.cn_display}
          </div>
          <h3 className="mt-0.5 text-lg font-semibold leading-snug">{p.name}</h3>
        </div>
        <StatusBadge status={actual ? "VERIFIED_2R" : "DEFAULT_USED"} label={actual ? t("report.actual_verified") : t("report.default_used")} />
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-x-3 gap-y-1">
        <div className="font-display text-[52px] font-semibold leading-none tracking-[-0.01em]">
          <LensNum node={p.see_node}>
            <AnimatedNumber value={p.see} format={(v) => n(v, 3)} countUp />
          </LensNum>
        </div>
        <div className="pb-1.5 text-sm text-muted">
          {t("report.see_short")} · t CO2 / t
        </div>
      </div>
      <div className="mt-1 text-[12px] text-muted">
        {t("report.see")} · {result!.period_label}
        {rp && <> · {t("report.inputs_verified", { good: rp.good, total: rp.total })}</>}
      </div>
      {bundle?.project.is_demo && p.id === "P1" && (
        <div className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-good/30 bg-goodbg px-2 py-1 text-[11px] text-goodink">
          <BadgeCheck className="h-3.5 w-3.5" /> {t("report.ec_ref", { v: n(p.see, 4) })}
        </div>
      )}

      <dl className="mt-5 grid grid-cols-3 gap-3 text-[13px]">
        <div className="rounded-xl bg-sunk px-3 py-2">
          <dt className="text-[11px] text-muted">{t("report.own")}</dt>
          <dd className="num text-base font-semibold"><LensNum node={`${p.id}.direct`}>{n(p.direct, 3)}</LensNum></dd>
        </div>
        <div className="rounded-xl bg-sunk px-3 py-2">
          <dt className="text-[11px] text-muted">{t("report.precursor")}</dt>
          <dd className="num text-base font-semibold"><LensNum node={`${p.id}.rod.contrib`}>{n(contrib, 3)}</LensNum></dd>
        </div>
        <div className="rounded-xl bg-sunk px-3 py-2">
          <dt className="text-[11px] text-muted">m · {t("report.m")}</dt>
          <dd className="num text-base font-semibold"><LensNum node={`${p.id}.rod.m`}>{n(p.m, 3)}</LensNum></dd>
        </div>
      </dl>

      <div className="mt-5">
        <div className="eyebrow mb-2">{t("report.contribution")}</div>
        <ContributionBar
          segments={p.contribution.map((c) => ({ key: c.key, label: c.key === "own" ? t("report.own") : `${p.precursor.name}`, value: Number(c.value), node: c.node, tag: c.key === "rod" ? (actual ? t("report.actual_verified") : t("report.default_used")) : undefined }))}
        />
      </div>

      <div className="mt-5 border-t border-line pt-4">
        <div className="eyebrow mb-2.5">{t("report.cost")}</div>
        <CostBars
          pickLabel={t("report.buyer_pays")}
          rows={[
            { key: "actual", label: t("report.your_data"), value: Number(b.cost_actual_eur), color: "--s1", display: <LensNum node={b.cost_actual_node}>{eur(b.cost_actual_eur)}</LensNum>, sub: onDefault ? undefined : inr(Number(b.cost_actual_eur) * fx), pick: !onDefault },
            { key: "default", label: t("report.eu_default"), value: Number(b.cost_default_eur), color: "--s2", display: <LensNum node={b.cost_default_node}>{eur(b.cost_default_eur)}</LensNum>, sub: onDefault ? inr(Number(b.cost_default_eur) * fx) : undefined, pick: onDefault },
          ]}
        />
        <p className={`mt-3 rounded-lg border px-3 py-2 text-[12px] leading-relaxed ${onDefault ? "border-warn/40 bg-warnbg text-warnink" : "border-good/30 bg-goodbg text-goodink"}`}>
          {onDefault
            ? t("report.basis_default", { actual: eur(b.actual_eur_t), def: eur(b.default_eur_t) })
            : t("report.basis_actual", { saving: eur(Number(b.cost_default_eur) - Number(b.cost_actual_eur)) })}
        </p>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-[12px] sm:grid-cols-4">
        {[
          { k: "sefa", label: t("report.sefa"), v: <LensNum node={p.sefa_node}>{n(p.sefa, 3)}</LensNum> },
          { k: "sefa_y", label: t("report.sefa_y"), v: <LensNum node={p.sefa_y_node}>{n(p.sefa_y, 3)}</LensNum> },
          { k: "exp", label: `${t("report.exported")} (${Object.keys(p.exports_by_quarter).map((q) => q.slice(-2)).join(", ") || "—"})`, v: <LensNum node={`${p.id}.exports`}>{n(p.exports_t, 1)} t</LensNum> },
          { k: "certs", label: t("report.certs"), v: <LensNum node={p.certificates_node}>{n(p.certificates_2026, 1)}</LensNum> },
        ].map((x) => (
          <div key={x.k} className="rounded-lg border border-line px-2.5 py-1.5">
            <dt className="truncate text-[11px] text-muted" title={x.label}>{x.label}</dt>
            <dd className="num text-[13px] font-semibold">{x.v}</dd>
          </div>
        ))}
      </dl>
    </motion.article>
  );
}

function Explanations() {
  const { t } = useTranslation();
  const { result } = useProject();
  const [more, setMore] = useState(false);
  return (
    <section className="card p-5">
      <h3 className="flex items-center gap-2 font-semibold">
        <BookOpenCheck className="h-4 w-4 text-muted" /> {t("report.explain")}
      </h3>
      <div className="mt-3 space-y-4">
        {result!.explanations.map((e) => (
          <div key={e.process}>
            <div className="text-[13px] font-semibold">{e.title}</div>
            <p className={`mt-1 text-[14px] leading-relaxed text-ink2 ${more ? "" : "line-clamp-3"}`}>{e.text}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {e.citations.map((c) => (
                <Link key={`${c.doc}${c.page}`} to={`/copilot?q=${encodeURIComponent(c.why)}`} className="chip transition-colors hover:border-accent/40 hover:text-accent">
                  {c.doc}, p. {c.page}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      {result!.explanations.length > 0 && (
        <button className="link mt-3 text-[13px]" onClick={() => setMore((m) => !m)} aria-expanded={more}>
          {more ? t("report.read_less") : t("report.read_more")}
        </button>
      )}
    </section>
  );
}

export function Exports() {
  const { t } = useTranslation();
  const { pid } = useProject();
  const toast = useToast();
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  async function create() {
    setBusy(true);
    try {
      const r = await api.share(pid);
      setLink(new URL(r.url, window.location.origin).toString());
      toast(t("toast.link_ready"));
    } finally {
      setBusy(false);
    }
  }
  const items = [
    { kind: "pdf" as const, icon: FileText, label: t("exports.pdf") },
    { kind: "xlsx" as const, icon: FileSpreadsheet, label: t("exports.xlsx") },
    { kind: "pack" as const, icon: FileArchive, label: t("exports.pack") },
  ];
  return (
    <section className="card p-5">
      <h3 className="font-semibold">{t("exports.title")}</h3>
      <div className="mt-3 grid gap-2">
        {items.map((it) => (
          <a key={it.kind} href={exportUrl(pid, it.kind)} className="btn-ghost group justify-start">
            <it.icon className="h-4 w-4 text-muted transition-colors group-hover:text-accent" /> {it.label}
          </a>
        ))}
        <Link to={`/p/${pid}/plan`} className="btn-ghost group justify-start">
          <ClipboardCheck className="h-4 w-4 text-muted transition-colors group-hover:text-accent" /> {t("exports.plan")}
        </Link>
      </div>
      <div id="buyer-link" className="mt-4 rounded-xl border border-line bg-sunk p-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Link2 className="h-4 w-4" /> {t("exports.buyer")}
        </div>
        <p className="mt-0.5 text-[12px] text-muted">{t("exports.buyer_d")}</p>
        {!link ? (
          <button className="btn-primary mt-2 w-full" onClick={create} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} {t("exports.create")}
          </button>
        ) : (
          <motion.div className="mt-2 flex gap-2" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <input readOnly value={link} className="min-h-[40px] min-w-0 flex-1 rounded-lg border border-line2 bg-surface px-2 font-mono text-[12px]" onFocus={(e) => e.target.select()} aria-label={t("exports.buyer")} />
            <button
              className="btn-ghost h-10 min-h-0 px-3"
              onClick={async () => {
                await navigator.clipboard.writeText(link);
                setCopied(true);
                toast(t("exports.copied"));
                setTimeout(() => setCopied(false), 1500);
              }}
              aria-label={t("exports.copy")}
            >
              {copied ? <Check className="h-4 w-4 animate-pop text-good" /> : <Copy className="h-4 w-4" />}
            </button>
            <a className="btn-ghost h-10 min-h-0 px-3" href={link} target="_blank" rel="noreferrer" aria-label={t("common.open")}>
              <ExternalLink className="h-4 w-4" />
            </a>
          </motion.div>
        )}
      </div>
    </section>
  );
}

function Checks() {
  const { t } = useTranslation();
  const { result } = useProject();
  const [open, setOpen] = useState(false);
  const checks = result!.checks;
  const attention = checks.filter((c) => c.status === "fail" || c.status === "warn");
  const passed = checks.filter((c) => c.status !== "fail" && c.status !== "warn");
  const nPass = checks.filter((c) => c.status === "pass").length;
  const row = (c: (typeof checks)[number]) => (
    <li key={c.id} className="flex flex-col gap-1 border-t border-line px-5 py-3 first:border-t-0 sm:flex-row sm:items-center sm:gap-4">
      <div className="w-24 shrink-0">
        <StatusBadge status={c.status} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{c.name}</div>
        <div className="text-[12px] text-muted">{c.formula}</div>
        {c.note && c.status !== "pass" && <div className="text-[12px] text-ink2">{c.note}</div>}
      </div>
      <div className="num text-[13px] text-ink2 sm:text-right">
        {c.result}
        <div className="text-[11px] text-muted">{c.tolerance}</div>
      </div>
    </li>
  );
  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">{t("report.checks")}</h3>
          <p className="text-[12px] text-muted">{t("report.checks_d")}</p>
        </div>
        <span className="text-[13px] text-ink2">{t("report.checks_summary", { pass: nPass, total: checks.length })}</span>
      </div>
      <ul>{attention.map(row)}</ul>
      {passed.length > 0 && (
        <>
          <Collapse open={open}>
            <ul className="border-t border-line">{passed.map(row)}</ul>
          </Collapse>
          <button className="flex min-h-[44px] w-full items-center gap-2 border-t border-line px-5 text-[13px] text-ink2 transition-colors hover:bg-sunk" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
            {open ? t("report.checks_hide") : t("report.checks_show", { count: passed.length })}
          </button>
        </>
      )}
    </section>
  );
}

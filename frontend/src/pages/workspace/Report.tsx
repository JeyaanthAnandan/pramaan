import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BadgeCheck, BookOpenCheck, Check, ClipboardCheck, Copy, ExternalLink, FileArchive, FileSpreadsheet, FileText, Link2, Loader2, MousePointerClick, ShieldAlert } from "lucide-react";
import { api, exportUrl, type ProcessResult } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, inr, n } from "@/lib/format";
import { LensNum } from "@/components/EvidenceLens";
import { ContributionBar, ReadinessRing } from "@/components/Charts";
import { StatusBadge } from "@/components/Status";
import { MoneySection } from "@/components/MoneySection";
import { Lever } from "@/components/Lever";
import { NoResult } from "./Gaps";

export default function Report() {
  const { t } = useTranslation();
  const { result } = useProject();
  const [whatIf, setWhatIf] = useState(false);
  if (!result) return <NoResult />;
  const procs = result.processes.filter((p) => p.see);
  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-2xl border border-warn/40 bg-warnbg px-4 py-3 text-[13px] text-warnink">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>
          <b>{t("app.provisional")}</b> {t("app.disclaimer")}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-5">
        <ReadinessRing value={Number(result.readiness.score)} size={84} label={t("report.readiness")} />
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-semibold tracking-tight">{t("report.title")}</h2>
          <p className="text-sm text-ink2">
            {t("report.readiness")}: <b className="num">{Number(result.readiness.score).toFixed(0)}%</b> {t("report.readiness_d")} ·{" "}
            {Object.entries(result.readiness.by_status).map(([k, v]) => `${t(`status.${k}`)}: ${v}`).join("; ")}
          </p>
          <p className="mt-1 flex items-center gap-1.5 text-[12px] text-muted">
            <MousePointerClick className="h-3.5 w-3.5" /> {t("report.click_hint")}
          </p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {procs.map((p) => (
          <ProcessCard key={p.id} p={p} />
        ))}
      </div>

      {procs.map((p) => (
        <Lever key={p.id} p={p} result={result} whatIf={whatIf} onWhatIf={setWhatIf} />
      )).reverse()}

      <MoneySection result={result} whatIf={whatIf} onWhatIf={setWhatIf} />

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Explanations />
        <Exports />
      </div>
      <Checks />
    </div>
  );
}

function ProcessCard({ p }: { p: ProcessResult }) {
  const { t } = useTranslation();
  const { result, bundle } = useProject();
  const tree = result!.calc_tree;
  const fx = Number(result!.money.fx.value);
  const actual = p.precursor.data === "ACTUAL_VERIFIED";
  const contrib = Number(tree[`${p.id}.rod.contrib`]?.value ?? 0);
  return (
    <article className="card min-w-0 p-5 sm:p-6">
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
        <div className="text-[52px] font-semibold leading-none tracking-[-0.03em]">
          <LensNum node={p.see_node}>{n(p.see, 3)}</LensNum>
        </div>
        <div className="pb-1.5 text-sm text-muted">
          {t("report.see_short")} · t CO2 / t
        </div>
      </div>
      <div className="mt-1 text-[12px] text-muted">{t("report.see")} · {result!.period_label}</div>
      {bundle?.project.is_demo && p.id === "P1" && (
        <div className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-good/30 bg-goodbg px-2 py-1 text-[11px] text-goodink">
          <BadgeCheck className="h-3.5 w-3.5" /> {t("report.ec_ref", { defaultValue: "Full precision {{v}} — matches EC Guidance 5d Example 3 (2.039 with rounded intermediates)", v: n(p.see, 4) })}
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

      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line pt-4 text-[13px]">
        <dt className="text-ink2">{t("report.sefa")}</dt>
        <dd className="num text-right font-medium"><LensNum node={p.sefa_node}>{n(p.sefa, 3)}</LensNum></dd>
        <dt className="text-ink2">{t("report.sefa_y")}</dt>
        <dd className="num text-right font-medium"><LensNum node={p.sefa_y_node}>{n(p.sefa_y, 3)}</LensNum></dd>
        <dt className="text-ink2">{t("report.exported")} (Q1–Q3)</dt>
        <dd className="num text-right font-medium"><LensNum node={`${p.id}.exports`}>{n(p.exports_t, 1)} t</LensNum></dd>
        <dt className="text-ink2">{t("report.certs")}</dt>
        <dd className="num text-right font-medium"><LensNum node={p.certificates_node}>{n(p.certificates_2026, 1)}</LensNum></dd>
        <dt className="text-ink2">{t("report.cost")}</dt>
        <dd className="num text-right font-semibold">
          <LensNum node={p.cost_node}>{eur(p.cost_2026_eur)}</LensNum>
          <span className="ml-1.5 font-normal text-muted">{inr(Number(p.cost_2026_eur) * fx)}</span>
        </dd>
      </dl>
    </article>
  );
}

function Explanations() {
  const { t } = useTranslation();
  const { result } = useProject();
  return (
    <section className="card p-5">
      <h3 className="flex items-center gap-2 font-semibold">
        <BookOpenCheck className="h-4 w-4 text-muted" /> {t("report.explain")}
      </h3>
      <div className="mt-3 space-y-4">
        {result!.explanations.map((e) => (
          <div key={e.process}>
            <div className="text-[13px] font-semibold">{e.title}</div>
            <p className="mt-1 text-[14px] leading-relaxed text-ink2">{e.text}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {e.citations.map((c) => (
                <Link key={`${c.doc}${c.page}`} to={`/copilot?q=${encodeURIComponent(c.why)}`} className="chip hover:border-accent/40 hover:text-accent">
                  {c.doc}, p. {c.page}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Exports() {
  const { t } = useTranslation();
  const { pid } = useProject();
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  async function create() {
    setBusy(true);
    try {
      const r = await api.share(pid);
      setLink(new URL(r.url, window.location.origin).toString());
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
          <a key={it.kind} href={exportUrl(pid, it.kind)} className="btn-ghost justify-start">
            <it.icon className="h-4 w-4 text-muted" /> {it.label}
          </a>
        ))}
        <Link to={`/p/${pid}/plan`} className="btn-ghost justify-start">
          <ClipboardCheck className="h-4 w-4 text-muted" /> {t("exports.plan")}
        </Link>
      </div>
      <div className="mt-4 rounded-xl border border-line bg-sunk p-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Link2 className="h-4 w-4" /> {t("exports.buyer")}
        </div>
        <p className="mt-0.5 text-[12px] text-muted">{t("exports.buyer_d")}</p>
        {!link ? (
          <button className="btn-primary mt-2 w-full" onClick={create} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} {t("exports.create")}
          </button>
        ) : (
          <div className="mt-2 flex gap-2">
            <input readOnly value={link} className="min-h-[40px] min-w-0 flex-1 rounded-lg border border-line2 bg-surface px-2 font-mono text-[12px]" onFocus={(e) => e.target.select()} />
            <button
              className="btn-ghost h-10 min-h-0 px-3"
              onClick={async () => {
                await navigator.clipboard.writeText(link);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              aria-label={t("exports.copy")}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
            <a className="btn-ghost h-10 min-h-0 px-3" href={link} target="_blank" rel="noreferrer" aria-label={t("common.open")}>
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        )}
      </div>
    </section>
  );
}

function Checks() {
  const { t } = useTranslation();
  const { result } = useProject();
  return (
    <section className="card overflow-hidden">
      <div className="border-b border-line px-5 py-3">
        <h3 className="font-semibold">{t("report.checks")}</h3>
        <p className="text-[12px] text-muted">{t("report.checks_d")}</p>
      </div>
      <ul className="divide-y divide-line">
        {result!.checks.map((c) => (
          <li key={c.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:gap-4">
            <div className="w-24 shrink-0">
              <StatusBadge status={c.status} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{c.name}</div>
              <div className="text-[12px] text-muted">{c.formula}</div>
            </div>
            <div className="num text-[13px] text-ink2 sm:text-right">
              {c.result}
              <div className="text-[11px] text-muted">{c.tolerance}</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

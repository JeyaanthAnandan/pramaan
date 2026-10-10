import { Link, NavLink, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Camera, ClipboardList, FileCheck2, Loader2 } from "lucide-react";
import { ProjectProvider, useProject } from "@/lib/project";
import { LensProvider } from "@/components/EvidenceLens";
import { ReadinessRing } from "@/components/Charts";
import { api } from "@/lib/api";
import { rememberProject } from "@/lib/session";
import Capture from "./workspace/Capture";
import Gaps from "./workspace/Gaps";
import Report from "./workspace/Report";
import { useEffect, useState } from "react";

export default function Workspace() {
  const { pid = "", step = "report" } = useParams();
  return (
    <ProjectProvider pid={pid}>
      <LensProvider>
        <Inner step={step} />
      </LensProvider>
    </ProjectProvider>
  );
}

function Inner({ step }: { step: string }) {
  const { t } = useTranslation();
  const { pid, bundle, result, loading, error } = useProject();
  useEffect(() => {
    if (bundle) rememberProject(pid);
  }, [bundle, pid]);
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);

  if (loading && !bundle)
    return (
      <div className="grid min-h-[50vh] place-items-center text-muted">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  if (error && !bundle)
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-warn" />
        <h1 className="mt-3 text-xl font-semibold">{t("common.error")}</h1>
        <p className="mt-1 text-sm text-muted">{String((error as Error).message)}</p>
        <button
          className="btn-primary mt-6"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await api.demoLoad();
              rememberProject(r.project_id);
              nav(`/p/${r.project_id}/report`);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} {t("landing.load")}
        </button>
      </div>
    );
  if (!bundle) return null;
  const p = bundle.project;
  const gaps = result?.gaps ?? [];
  const red = gaps.filter((g) => g.status === "red").length;
  const amber = gaps.filter((g) => g.status === "amber").length;
  const steps = [
    { key: "capture", icon: Camera, n: 1, label: t("steps.capture"), q: t("steps.capture_q"), meta: `${bundle.documents.length}` },
    { key: "gaps", icon: ClipboardList, n: 2, label: t("steps.gaps"), q: t("steps.gaps_q"), meta: result ? `${red}·${amber}` : "" },
    { key: "report", icon: FileCheck2, n: 3, label: t("steps.report"), q: t("steps.report_q"), meta: result ? `${Number(result.readiness.score).toFixed(0)}%` : "" },
  ];
  return (
    <div className="mx-auto max-w-7xl px-4 pb-10 pt-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {p.is_demo && <span className="chip border-warn/40 bg-warnbg text-warnink">{t("app.sample")}</span>}
            {result?.mode && <span className="chip">{result.mode === "live" ? t("app.live") : t("app.replay")}</span>}
          </div>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight sm:truncate sm:text-[28px]">{p.company}</h1>
          <p className="text-sm text-muted">
            {p.city} · {p.country} · {p.period_label}
          </p>
        </div>
        {result && (
          <Link to={`/p/${pid}/report`} className="hidden items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2 shadow-card sm:flex">
            <ReadinessRing value={Number(result.readiness.score)} size={56} />
            <div className="text-[12px] leading-tight">
              <div className="font-semibold">{t("report.readiness")}</div>
              <div className="max-w-[160px] text-muted">{t("report.readiness_d")}</div>
            </div>
          </Link>
        )}
      </div>
      <nav className="mt-6 grid grid-cols-3 gap-2" aria-label="Steps">
        {steps.map((s) => (
          <NavLink
            key={s.key}
            to={`/p/${pid}/${s.key}`}
            className={({ isActive }) =>
              `group relative flex min-h-[56px] min-w-0 flex-col items-start justify-center gap-1 rounded-2xl border px-2.5 py-2 transition sm:flex-row sm:items-center sm:gap-3 sm:px-4 ${isActive || step === s.key ? "border-ink bg-surface shadow-card" : "border-line bg-transparent hover:bg-surface"}`
            }
          >
            <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold sm:h-8 sm:w-8 sm:text-sm ${step === s.key ? "bg-ink text-page" : "bg-sunk text-ink2"}`}>{s.n}</span>
            <span className="min-w-0 max-w-full">
              <span className="block text-[13px] font-semibold leading-tight sm:truncate sm:text-sm">{s.label}</span>
              <span className="hidden truncate text-[12px] text-muted sm:block">{s.q}</span>
            </span>
            {s.meta && <span className="num ml-auto hidden rounded-full bg-sunk px-2 py-0.5 text-[11px] text-ink2 md:inline">{s.meta}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="mt-6">
        {step === "capture" && <Capture />}
        {step === "gaps" && <Gaps />}
        {step === "report" && <Report />}
      </div>
    </div>
  );
}

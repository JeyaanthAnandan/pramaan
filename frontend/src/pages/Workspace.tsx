import { Link, NavLink, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, useAnimate } from "motion/react";
import { AlertTriangle, Check, Compass, KeyRound, Loader2 } from "lucide-react";
import { ProjectProvider, useProject } from "@/lib/project";
import { LensProvider } from "@/components/EvidenceLens";
import { AskProvider } from "@/components/ReportAsk";
import { TourProvider, useTour } from "@/components/Tour";
import { ReadinessRing } from "@/components/Charts";
import { WorkspaceSkeleton } from "@/components/Skeleton";
import { api, ApiError } from "@/lib/api";
import { rememberPasscode, rememberProject } from "@/lib/session";
import { EASE, SPRING } from "@/lib/motion";
import { periodLabel } from "@/lib/format";
import Capture from "./workspace/Capture";
import Gaps from "./workspace/Gaps";
import Report from "./workspace/Report";
import { useEffect, useRef, useState } from "react";

const ORDER: Record<string, number> = { capture: 0, gaps: 1, report: 2 };

export default function Workspace() {
  const { pid = "", step = "report" } = useParams();
  return (
    <ProjectProvider pid={pid}>
      <LensProvider>
        <AskProvider>
          <TourProvider>
            <Inner step={step} />
          </TourProvider>
        </AskProvider>
      </LensProvider>
    </ProjectProvider>
  );
}

function Inner({ step }: { step: string }) {
  const { t, i18n } = useTranslation();
  const { pid, bundle, result, loading, error, refresh } = useProject();
  const tour = useTour();
  // a handoff link from the owner's laptop carries the passcode in its #fragment: unlock, then forget it
  useEffect(() => {
    const m = window.location.hash.match(/(?:^#|&)k=([A-Za-z0-9-]{6,40})/);
    if (!m) return;
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    api
      .unlock(pid, m[1])
      .then(() => {
        rememberPasscode(pid, m[1]);
        return refresh();
      })
      .catch(() => undefined); // a wrong or old code: the passcode form is still there
  }, [pid, refresh]);
  useEffect(() => {
    if (bundle) rememberProject(pid);
  }, [bundle, pid]);
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  // steps slide in the direction you move: forward from the right, back from the left
  const prev = useRef(step);
  const dir = (ORDER[step] ?? 0) >= (ORDER[prev.current] ?? 0) ? 1 : -1;
  useEffect(() => {
    prev.current = step;
  }, [step]);

  if (loading && !bundle) return <WorkspaceSkeleton />;
  if (error && !bundle && error instanceof ApiError && error.status === 401) return <Unlock />;
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
    { key: "capture", n: 1, label: t("steps.capture"), q: t("steps.capture_q"), done: !!result },
    { key: "gaps", n: 2, label: t("steps.gaps"), q: t("steps.gaps_q"), done: !!result && red + amber === 0 },
    { key: "report", n: 3, label: t("steps.report"), q: t("steps.report_q"), done: false },
  ];
  return (
    <div className="mx-auto max-w-7xl px-4 pb-10 pt-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {p.is_demo && <span className="chip border-warn/40 bg-warnbg text-warnink">{t("app.sample")}</span>}
            {result?.mode && <span className="chip">{result.mode === "live" ? t("app.live") : t("app.replay")}</span>}
            {p.is_demo && result && (
              <button className="chip border-accent/30 bg-accent/5 text-accent transition hover:bg-accent/10" onClick={tour}>
                <Compass className="h-3 w-3" aria-hidden /> {t("tour.start")}
              </button>
            )}
          </div>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight sm:truncate sm:text-[28px]">{p.company}</h1>
          <p className="text-sm text-muted">{[p.city, p.country, periodLabel(p.months, p.period_label, i18n.language, t("app.provisional_ytd"))].filter(Boolean).join(" · ")}</p>
        </div>
        {result && step !== "report" && (
          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.3, ease: EASE }} className="hidden sm:block">
            <Link to={`/p/${pid}/report`} className="card-hover flex items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2 shadow-card">
              <ReadinessRing value={Number(result.readiness.score)} size={56} stroke={6} label={t("report.readiness")} />
              <div className="text-[12px] leading-tight">
                <div className="font-semibold">{t("report.readiness")}</div>
                <div className="max-w-[170px] text-muted">{t("report.readiness_d")}</div>
                {result.readiness.lines_total > 0 && (
                  <div className={`mt-0.5 max-w-[170px] font-semibold ${result.readiness.lines_ready === result.readiness.lines_total ? "text-goodink" : "text-warnink"}`}>
                    {t("report.lines_ready", { ready: result.readiness.lines_ready, total: result.readiness.lines_total })}
                  </div>
                )}
              </div>
            </Link>
          </motion.div>
        )}
      </div>
      <nav className="mt-6 grid grid-cols-3 gap-2" aria-label="Steps">
        {steps.map((s) => {
          const on = step === s.key;
          return (
            <NavLink
              key={s.key}
              to={`/p/${pid}/${s.key}`}
              aria-current={on ? "step" : undefined}
              className={`group relative flex min-h-[56px] min-w-0 flex-col items-start justify-center gap-1 rounded-2xl border px-2.5 py-2 transition-colors sm:flex-row sm:items-center sm:gap-3 sm:px-4 ${on ? "border-transparent" : "border-line hover:border-line2 hover:bg-surface/70"}`}
            >
              {on && <motion.span layoutId="step-pill" className="absolute inset-0 rounded-2xl border border-ink bg-surface shadow-card" transition={SPRING} aria-hidden />}
              <span className={`relative grid h-6 w-6 shrink-0 place-items-center rounded font-mono text-xs font-semibold transition-colors duration-300 sm:h-8 sm:w-8 sm:text-sm ${on ? "bg-ink text-page" : s.done ? "bg-goodbg text-goodink" : "bg-sunk text-ink2"}`}>
                {s.done && !on ? <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4" aria-label="done" /> : s.n}
              </span>
              <span className="relative min-w-0 max-w-full">
                <span className="block text-[13px] font-semibold leading-tight sm:truncate sm:text-sm">{s.label}</span>
                <span className="hidden truncate text-[12px] text-muted sm:block">{s.q}</span>
              </span>
              <span className="relative ml-auto hidden items-center gap-1 md:flex">
                {s.key === "capture" && <span className="num rounded-full bg-sunk px-2 py-0.5 text-[11px] text-ink2">{bundle.documents.length}</span>}
                {s.key === "gaps" && result && (
                  <>
                    {red > 0 && <span className="num inline-flex items-center gap-1 rounded-full bg-badbg px-2 py-0.5 text-[11px] font-semibold text-badink"><span className="h-1.5 w-1.5 rounded-full bg-bad" aria-hidden />{red}</span>}
                    {amber > 0 && <span className="num inline-flex items-center gap-1 rounded-full bg-warnbg px-2 py-0.5 text-[11px] font-semibold text-warnink"><span className="h-1.5 w-1.5 rounded-full bg-warn" aria-hidden />{amber}</span>}
                  </>
                )}
                {s.key === "report" && result && <span className="num rounded-full bg-sunk px-2 py-0.5 text-[11px] text-ink2">{Number(result.readiness.score).toFixed(0)}%</span>}
              </span>
            </NavLink>
          );
        })}
      </nav>
      <motion.div key={step} className="mt-6" initial={{ opacity: 0, x: dir * 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.32, ease: EASE }}>
        {step === "capture" && <Capture />}
        {step === "gaps" && <Gaps />}
        {step === "report" && <Report />}
      </motion.div>
    </div>
  );
}

function Unlock() {
  const { t } = useTranslation();
  const { pid, refresh } = useProject();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [field, shake] = useAnimate<HTMLInputElement>(); // a wrong code shakes the field
  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <motion.form
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: EASE }}
        className="card p-6"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await api.unlock(pid, code);
            await refresh();
          } catch (x) {
            setErr((x as Error).message);
            if (field.current) void shake(field.current, { x: [0, -8, 7, -5, 3, 0] }, { duration: 0.4 });
          } finally {
            setBusy(false);
          }
        }}
      >
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/10">
          <KeyRound className="h-6 w-6 text-accent" aria-hidden />
        </span>
        <h1 className="mt-3 text-xl font-semibold">{t("unlock.title")}</h1>
        <p className="mt-1 text-sm text-ink2">{t("unlock.lead")}</p>
        <label className="mt-4 block text-[13px]">
          <span className="text-ink2">{t("unlock.label")}</span>
          <input
            ref={field}
            value={code}
            onChange={(e) => {
              // XXXX-XXXX-XXXX as you type (no look-alike characters are ever issued)
              const raw = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
              setCode(raw.match(/.{1,4}/g)?.join("-") ?? "");
            }}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder="XXXX-XXXX-XXXX"
            className="mt-1 min-h-[48px] w-full rounded-xl border border-line2 bg-surface px-3 text-center font-mono text-[18px] tracking-[0.18em] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          />
        </label>
        {err && <p className="mt-2 text-[13px] text-badink">{err}</p>}
        <button className="btn-primary mt-4 w-full" disabled={busy || code.replace(/[^a-z0-9]/gi, "").length < 12}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} {t("unlock.open")}
        </button>
      </motion.form>
    </div>
  );
}

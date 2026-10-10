import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bot, Calculator, CheckCircle2, ChevronDown, CircleDashed, ClipboardCheck, FileSearch, FileText, Hand, Inbox, Loader2, MessageSquareText, ScanEye, ShieldCheck, Tags, XCircle } from "lucide-react";
import type { TimelineEvent } from "@/lib/api";
import { ms } from "@/lib/format";

const AGENTS: { key: string; icon: typeof Bot; desc: string }[] = [
  { key: "Intake", icon: Inbox, desc: "Receives photos and PDFs" },
  { key: "Classifier", icon: Tags, desc: "Document type, language, period" },
  { key: "Extractor", icon: FileSearch, desc: "Every value with its region (box_2d)" },
  { key: "SecondReader", icon: ScanEye, desc: "Blind re-read of each cropped region" },
  { key: "HumanReview", icon: Hand, desc: "Disagreements wait for your tap" },
  { key: "ControlChecks", icon: ClipboardCheck, desc: "Mass balance, stock, invoices (code)" },
  { key: "Calculator", icon: Calculator, desc: "Deterministic CBAM engine (Decimal)" },
  { key: "GapFinder", icon: ShieldCheck, desc: "Required-data checklist" },
  { key: "Explainer", icon: MessageSquareText, desc: "Plain language with page citations" },
  { key: "Reporter", icon: FileText, desc: "Report, workbook, pack, buyer link" },
];

export function useRunEvents(pid: string, runId: string | null | undefined, onEnd?: (status: string) => void) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [ended, setEnded] = useState<string | null>(null);
  const endRef = useRef(onEnd);
  endRef.current = onEnd;
  useEffect(() => {
    setEvents([]);
    setEnded(null);
    if (!runId) return;
    const es = new EventSource(`/api/projects/${pid}/runs/${runId}/events`);
    es.addEventListener("timeline", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as TimelineEvent;
      setEvents((xs) => (xs.some((x) => x.seq === ev.seq) ? xs : [...xs, ev]));
    });
    es.addEventListener("end", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setEnded(d.status);
      endRef.current?.(d.status);
      es.close();
    });
    es.onerror = () => es.close();
    return () => es.close();
  }, [pid, runId]);
  return { events, ended };
}

export function AgentTimeline({ events, ended, mode, compact = false }: { events: TimelineEvent[]; ended: string | null; mode?: string | null; compact?: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState<string | null>(null);
  const byAgent = useMemo(() => {
    const m: Record<string, TimelineEvent[]> = {};
    events.forEach((e) => (m[e.agent] ??= []).push(e));
    return m;
  }, [events]);
  const failed = events.filter((e) => e.agent === "Workflow" && e.status === "error");
  const totalTokens = events.reduce((a, e) => a + (e.tokens_in ?? 0) + (e.tokens_out ?? 0), 0);
  const started = events[0]?.ts;
  const last = events[events.length - 1]?.ts;
  const span = started && last ? (new Date(last).getTime() - new Date(started).getTime()) : 0;

  if (!events.length) return <p className="px-1 py-6 text-center text-sm text-muted">{t("timeline.empty")}</p>;

  return (
    <div>
      <ol className="relative" aria-live="polite" aria-label={t("timeline.title")}>
        {AGENTS.map(({ key, icon: Icon, desc }, i) => {
          const evs = byAgent[key] ?? [];
          const done = evs.filter((e) => e.status === "done");
          const starts = evs.filter((e) => e.status === "start");
          const errs = evs.filter((e) => e.status === "error");
          const reviews = evs.filter((e) => e.status === "review");
          const isRunning = !ended && starts.length > done.length;
          const state = errs.length ? "error" : reviews.length ? "review" : isRunning ? "running" : done.length ? "done" : "pending";
          if (key === "HumanReview" && !reviews.length && state === "pending" && ended) return null;
          const lastDone = done[done.length - 1] ?? reviews[reviews.length - 1];
          const dur = done.reduce((a, e) => Math.max(a, e.duration_ms ?? 0), 0);
          const model = [...evs].reverse().find((e) => e.model)?.model;
          const toks = evs.reduce((a, e) => a + (e.tokens_in ?? 0) + (e.tokens_out ?? 0), 0);
          const perDoc = key === "Classifier" || key === "Extractor";
          const isOpen = open === key;
          return (
            <li key={key} className="relative pb-1 pl-9">
              {i < AGENTS.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-20px)] w-px bg-line" aria-hidden />}
              <span
                className={`absolute left-0 top-1.5 grid h-[31px] w-[31px] place-items-center rounded-full border ${
                  state === "done" ? "border-good/40 bg-goodbg text-goodink" : state === "running" ? "border-accent/40 bg-accent/10 text-accent" : state === "review" ? "border-warn/50 bg-warnbg text-warnink" : state === "error" ? "border-bad/40 bg-badbg text-badink" : "border-line bg-sunk text-muted"
                }`}
              >
                {state === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" aria-hidden />}
              </span>
              <button type="button" className="w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-sunk" onClick={() => setOpen(isOpen ? null : key)} aria-expanded={isOpen}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{key}</span>
                  {perDoc && (starts.length > 0 || done.length > 0) && (
                    <span className="num text-[11px] text-muted">
                      {done.length}/{Math.max(starts.length, done.length)}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-1 text-[11px] text-muted">
                    {state === "done" && <CheckCircle2 className="h-3.5 w-3.5 text-good" />}
                    {state === "error" && <XCircle className="h-3.5 w-3.5 text-bad" />}
                    {state === "pending" && <CircleDashed className="h-3.5 w-3.5" />}
                    {dur > 0 && <span className="num">{ms(dur)}</span>}
                    <ChevronDown className={`h-3.5 w-3.5 transition ${isOpen ? "rotate-180" : ""}`} />
                  </span>
                </div>
                {!compact && <div className="text-[12px] text-ink2">{state === "pending" ? desc : lastDone?.output_summary || evs[evs.length - 1]?.output_summary || desc}</div>}
                {(model || toks > 0) && (
                  <div className="mt-0.5 flex flex-wrap gap-1.5">
                    {model && <span className="chip font-mono">{model}</span>}
                    {toks > 0 && <span className="chip num">{toks.toLocaleString()} {t("timeline.tokens")}</span>}
                  </div>
                )}
              </button>
              {isOpen && (
                <ul className="mb-2 ml-2 mt-1 max-h-56 space-y-1 overflow-y-auto border-l border-line pl-3 text-[12px]">
                  {evs.filter((e) => e.status !== "start").map((e) => (
                    <li key={e.seq} className="text-ink2">
                      <span className="text-muted">{e.input_summary}</span> {e.input_summary && "→"} {e.output_summary}
                      {e.duration_ms ? <span className="num text-muted"> · {ms(e.duration_ms)}</span> : null}
                    </li>
                  ))}
                  {!evs.length && <li className="text-muted">{desc}</li>}
                </ul>
              )}
            </li>
          );
        })}
      </ol>
      {failed.map((f) => (
        <p key={f.seq} className="mt-2 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-xs text-badink">{f.output_summary}</p>
      ))}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-[11px] text-muted">
        {mode && <span>{t("timeline.mode")}: <b className="text-ink2">{mode}</b></span>}
        {span > 0 && <span>{t("timeline.duration")}: <b className="num text-ink2">{ms(span)}</b></span>}
        <span>{t("timeline.tokens")}: <b className="num text-ink2">{totalTokens.toLocaleString()}</b></span>
        {ended && <span className="text-goodink">● {t(`timeline.${ended === "done" ? "done" : "error"}`)}</span>}
        {!ended && <span className="text-accent">● {t("timeline.running")}</span>}
      </div>
    </div>
  );
}

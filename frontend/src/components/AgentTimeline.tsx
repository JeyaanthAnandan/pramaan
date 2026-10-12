import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Collapse, EASE } from "@/lib/motion";
import { Bot, Boxes, Calculator, CheckCircle2, ChevronDown, CircleDashed, ClipboardCheck, FileSearch, FileText, Hand, Inbox, Loader2, MessageSquareText, ScanEye, ShieldCheck, Tags, XCircle } from "lucide-react";
import type { TimelineEvent } from "@/lib/api";
import { ms } from "@/lib/format";

const AGENTS: { key: string; icon: typeof Bot; desc: string }[] = [
  { key: "Intake", icon: Inbox, desc: "Receives photos and PDFs" },
  { key: "Classifier", icon: Tags, desc: "Document type, language, period" },
  { key: "ProductLines", icon: Boxes, desc: "Product lines from your invoices (CN codes checked)" },
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
  // while a run is going the duration ticks every second (server time at the last event + the local
  // time since it arrived, so a skewed phone clock cannot make it jump)
  const [now, setNow] = useState(() => Date.now());
  const seen = useRef<{ ts?: string; at: number }>({ at: Date.now() });
  useEffect(() => {
    seen.current = { ts: last, at: Date.now() };
  }, [last]);
  useEffect(() => {
    if (ended || !started) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [ended, started]);
  const span = started && last ? new Date(last).getTime() - new Date(started).getTime() + (ended ? 0 : Math.max(0, now - seen.current.at)) : 0;

  if (!events.length) return <p className="px-1 py-6 text-center text-sm text-muted">{t("timeline.empty")}</p>;

  const states = AGENTS.map(({ key }) => {
    const evs = byAgent[key] ?? [];
    const done = evs.filter((e) => e.status === "done").length;
    const starts = evs.filter((e) => e.status === "start").length;
    if (evs.some((e) => e.status === "error")) return "error";
    if (evs.some((e) => e.status === "review")) return "review";
    if (!ended && starts > done) return "running";
    return done ? "done" : "pending";
  });
  const visible = AGENTS.filter(({ key }, i) => !(key === "HumanReview" && states[i] === "pending" && ended));
  const finished = states.filter((st, i) => visible.includes(AGENTS[i]) && (st === "done" || st === "review")).length;
  const progress = ended ? 1 : finished / Math.max(1, visible.length);

  return (
    <div>
      {/* how far the run has got: fills as each agent finishes */}
      <div className="mb-3 h-1 overflow-hidden rounded-full bg-sunk" aria-hidden>
        <motion.div className={`h-full rounded-full ${failed.length ? "bg-bad" : ended ? "bg-good" : "bg-accent"}`} initial={false} animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.5, ease: EASE }} />
      </div>
      <ol className="relative" aria-live="polite" aria-label={t("timeline.title")}>
        {AGENTS.map(({ key, icon: Icon, desc }, i) => {
          const evs = byAgent[key] ?? [];
          const done = evs.filter((e) => e.status === "done");
          const starts = evs.filter((e) => e.status === "start");
          const reviews = evs.filter((e) => e.status === "review");
          const state = states[i];
          if (key === "HumanReview" && !reviews.length && state === "pending" && ended) return null;
          const lastDone = done[done.length - 1] ?? reviews[reviews.length - 1];
          const dur = done.reduce((a, e) => Math.max(a, e.duration_ms ?? 0), 0);
          const model = [...evs].reverse().find((e) => e.model)?.model;
          const toks = evs.reduce((a, e) => a + (e.tokens_in ?? 0) + (e.tokens_out ?? 0), 0);
          const perDoc = key === "Classifier" || key === "Extractor";
          const isOpen = open === key;
          const passed = state === "done" || state === "review";
          return (
            <li key={key} className="relative pb-1 pl-9">
              {i < AGENTS.length - 1 && (
                <span className="absolute left-[15px] top-8 h-[calc(100%-20px)] w-px bg-line" aria-hidden>
                  <motion.span className="absolute inset-x-0 top-0 block bg-good/60" initial={false} animate={{ height: passed ? "100%" : "0%" }} transition={{ duration: 0.4, ease: EASE }} />
                </span>
              )}
              <span
                className={`absolute left-0 top-1.5 grid h-[31px] w-[31px] place-items-center rounded-full border transition-colors duration-300 ${
                  state === "done" ? "border-good/40 bg-goodbg text-goodink" : state === "running" ? "border-accent/40 bg-accent/10 text-accent" : state === "review" ? "border-warn/50 bg-warnbg text-warnink" : state === "error" ? "border-bad/40 bg-badbg text-badink" : "border-line bg-sunk text-muted"
                }`}
              >
                {state === "running" && <span className="absolute inset-0 animate-ping rounded-full bg-accent/25" aria-hidden />}
                <Icon key={state} className={`relative h-4 w-4 ${state === "done" || state === "review" ? "animate-pop" : ""}`} aria-hidden />
              </span>
              <button type="button" className="w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-sunk" onClick={() => setOpen(isOpen ? null : key)} aria-expanded={isOpen}>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-semibold ${state === "pending" ? "text-ink2" : ""}`}>{key}</span>
                  {perDoc && (starts.length > 0 || done.length > 0) && (
                    <span className="num text-[11px] text-muted">
                      {done.length}/{Math.max(starts.length, done.length)}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-1 text-[11px] text-muted">
                    {state === "done" && <CheckCircle2 className="h-3.5 w-3.5 animate-pop text-good" />}
                    {state === "error" && <XCircle className="h-3.5 w-3.5 text-bad" />}
                    {state === "pending" && <CircleDashed className="h-3.5 w-3.5" />}
                    {state === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
                    {dur > 0 && <span className="num">{ms(dur)}</span>}
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
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
              <Collapse open={isOpen}>
                <ul className="mb-2 ml-2 mt-1 max-h-56 space-y-1 overflow-y-auto border-l border-line pl-3 text-[12px]">
                  {evs.filter((e) => e.status !== "start").map((e) => (
                    <li key={e.seq} className="text-ink2">
                      <span className="text-muted">{e.input_summary}</span> {e.input_summary && "→"} {e.output_summary}
                      {e.duration_ms ? <span className="num text-muted"> · {ms(e.duration_ms)}</span> : null}
                    </li>
                  ))}
                  {!evs.length && <li className="text-muted">{desc}</li>}
                </ul>
              </Collapse>
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
        {!ended && (
          <span className="inline-flex items-center gap-1 text-accent">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            {t("timeline.running")}
          </span>
        )}
      </div>
    </div>
  );
}

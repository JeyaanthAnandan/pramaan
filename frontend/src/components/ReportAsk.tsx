import { createContext, Fragment, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "motion/react";
import { BookOpen, Loader2, MessageCircleQuestion, ScanSearch, SendHorizonal, ShieldCheck, Sparkles, X } from "lucide-react";
import { api, type ReportAnswer, type ReportFact } from "@/lib/api";
import { useProject } from "@/lib/project";
import { EASE, rise, stagger } from "@/lib/motion";
import { useLens } from "./EvidenceLens";
import { useReturnFocus } from "@/lib/focus";

interface Turn { q: string; a?: ReportAnswer; err?: string }
const AskCtx = createContext<(q?: string) => void>(() => {});
/** Open the "Ask about this report" panel, optionally with a question already asked. */
export const useAsk = () => useContext(AskCtx);

const SUGGEST = ["q_default", "q_pay", "q_first", "q_gas", "q_dv", "q_rod"] as const;
const TOKEN = /(\[F:[A-Za-z0-9_.-]+\]|\[Guidance [^\],]+, p\. ?\d+\])/g;

/** Ask about this report: questions about the factory's own figures, answered from the engine's
 *  numbers (each one opens the Evidence Lens) and the EC guidance. Non-modal, so the lens can open
 *  over it and the conversation is still there when the lens closes. */
export function AskProvider({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const { pid, result } = useProject();
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const ask = useCallback(
    async (question: string, node?: string) => {
      const text = question.trim();
      if (!text || busy) return;
      setBusy(true);
      setQ("");
      setTurns((xs) => [...xs, { q: text }]);
      try {
        const a = await api.reportAsk(pid, text, i18n.language, node);
        setTurns((xs) => xs.map((x, i) => (i === xs.length - 1 ? { ...x, a } : x)));
      } catch (e) {
        setTurns((xs) => xs.map((x, i) => (i === xs.length - 1 ? { ...x, err: (e as Error).message } : x)));
      } finally {
        setBusy(false);
      }
    },
    [busy, pid, i18n.language],
  );
  const focus = useReturnFocus('[data-fab="ask"]');
  const { remember } = focus;
  const openAsk = useCallback(
    (question?: string, node?: string) => {
      remember();
      setOpen(true);
      if (question) void ask(question, node);
    },
    [ask, remember],
  );
  // the Evidence Lens asks for a plain-words explanation of one number (it sits above this provider,
  // so it learns that the panel exists from a flag on <html>)
  useEffect(() => {
    document.documentElement.dataset.ask = "1";
    return () => {
      delete document.documentElement.dataset.ask;
    };
  }, []);
  useEffect(() => {
    const f = (e: Event) => {
      const d = (e as CustomEvent<{ q: string; node: string }>).detail;
      if (d?.q) openAsk(d.q, d.node);
    };
    window.addEventListener("pramaan:ask", f);
    return () => window.removeEventListener("pramaan:ask", f);
  }, [openAsk]);

  return (
    <AskCtx.Provider value={openAsk}>
      {children}
      {result && (
        <AnimatePresence>
          {!open && (
            <motion.button
              key="fab"
              className="fixed bottom-5 right-5 z-20 inline-flex min-h-[48px] items-center gap-2 rounded-full bg-ink px-4 text-sm font-semibold text-page shadow-lift transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-page"
              initial={{ opacity: 0, y: 16, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.9 }}
              transition={{ type: "spring", stiffness: 420, damping: 30 }}
              onClick={() => openAsk()}
              data-fab="ask"
            >
              <Sparkles className="h-4 w-4 text-[#7dd3a8]" aria-hidden /> {t("ask.fab")}
            </motion.button>
          )}
        </AnimatePresence>
      )}
      <Dialog.Root open={open} onOpenChange={setOpen} modal={false}>
        <Dialog.Portal>
          <Dialog.Content
            onCloseAutoFocus={focus.onCloseAutoFocus}
            onInteractOutside={(e) => e.preventDefault()}
            onOpenAutoFocus={(e) => {
              e.preventDefault();
              input.current?.focus();
            }}
            className="fixed inset-y-0 right-0 z-30 flex w-full max-w-[460px] flex-col border-l border-line bg-page shadow-lift focus:outline-none data-[state=closed]:animate-sheetout data-[state=open]:animate-sheet"
            aria-describedby="ask-lead"
          >
            <div className="flex items-start gap-3 border-b border-line px-4 py-3">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-ink text-[#7dd3a8]">
                <Sparkles className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <Dialog.Title className="font-semibold">{t("ask.title")}</Dialog.Title>
                <p id="ask-lead" className="text-[12px] text-muted">{t("ask.lead")}</p>
              </div>
              <Dialog.Close className="btn-quiet" aria-label={t("common.close")}>
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4" aria-live="polite">
              {!turns.length && (
                <motion.div variants={stagger(0.05, 0.1)} initial="hidden" animate="show" className="space-y-2">
                  <div className="eyebrow">{t("copilot.examples")}</div>
                  {SUGGEST.map((k) => (
                    <motion.button key={k} variants={rise} className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2.5 text-left text-[14px] text-ink2 shadow-card transition hover:-translate-y-0.5 hover:border-accent/40 hover:text-accent disabled:opacity-50" onClick={() => void ask(t(`ask.${k}`))} disabled={busy}>
                      <MessageCircleQuestion className="h-4 w-4 shrink-0 text-muted" aria-hidden />
                      {t(`ask.${k}`)}
                    </motion.button>
                  ))}
                </motion.div>
              )}
              {turns.map((turn, i) => (
                <div key={i} className="space-y-3">
                  <motion.div className="ml-auto w-fit max-w-[88%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-[14px] text-page" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }}>
                    {turn.q}
                  </motion.div>
                  {!turn.a && !turn.err && (
                    <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md border border-line bg-surface px-3.5 py-2.5 text-[13px] text-muted shadow-card">
                      <span className="flex gap-1" aria-hidden>
                        {[0, 1, 2].map((d) => (
                          <motion.span key={d} className="h-1.5 w-1.5 rounded-full bg-accent" animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }} transition={{ duration: 1, repeat: Infinity, delay: d * 0.15 }} />
                        ))}
                      </span>
                      {t("ask.thinking")}
                    </div>
                  )}
                  {turn.err && <p className="rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{turn.err}</p>}
                  {turn.a && <Answer a={turn.a} />}
                </div>
              ))}
              <div ref={end} />
            </div>
            <form
              className="flex gap-2 border-t border-line p-3"
              onSubmit={(e) => {
                e.preventDefault();
                void ask(q);
              }}
            >
              <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ask.placeholder")} aria-label={t("ask.placeholder")} maxLength={500} className="input min-w-0 flex-1 text-[15px]" />
              <button className="btn-primary" disabled={busy || !q.trim()} aria-label={t("copilot.ask")}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
              </button>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </AskCtx.Provider>
  );
}

function Answer({ a }: { a: ReportAnswer }) {
  const { t } = useTranslation();
  const byId: Record<string, ReportFact> = {};
  a.facts.forEach((f) => (byId[f.id] = f));
  const used = (a.mode === "grounded" ? a.cited ?? [] : a.relevant).filter((id, i, xs) => byId[id] && xs.indexOf(id) === i).map((id) => byId[id]);
  // a cited figure with no lens node (a sum) is listed below; in the text its marker goes, with the space before it
  const text = (a.answer ?? "").replace(/\s*\[F:([A-Za-z0-9_.-]+)\]/g, (m, id: string) => (byId[id]?.node ? m : ""));
  return (
    <motion.div className="card space-y-3 p-4" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
      {a.answer ? (
        <p className="text-[15px] leading-relaxed">
          {text.split(TOKEN).map((part, i) => {
            const f = part.match(/^\[F:(.+)\]$/);
            if (f) return byId[f[1]] ? <FactChip key={i} f={byId[f[1]]} /> : null;
            const g = part.match(/^\[(Guidance [^\],]+), p\. ?(\d+)\]$/);
            if (g)
              return (
                <span key={i} className="mx-0.5 inline-flex items-center gap-1 whitespace-nowrap rounded border border-line bg-sunk px-1 align-[1px] text-[11px] text-ink2">
                  <BookOpen className="h-3 w-3" aria-hidden /> {g[1]}, {t("copilot.page")} {g[2]}
                </span>
              );
            return <Fragment key={i}>{part}</Fragment>;
          })}
        </p>
      ) : (
        <p className="text-[13px] text-ink2">{t(`ask.note_${a.note ?? "no_gemini"}`)}</p>
      )}
      {a.answer && a.guard && a.guard.numbers > 0 && (
        <p className="flex items-center gap-1.5 text-[11px] text-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-good" aria-hidden />
          {t("ask.checked", { count: a.guard.numbers })}
          {a.guard.repaired.length > 0 && <> · {t("ask.repaired")}</>}
        </p>
      )}
      {used.length > 0 && (
        <div>
          <div className="eyebrow mb-1">{t("ask.figures")}</div>
          <motion.ul className="divide-y divide-line rounded-xl border border-line" variants={stagger(0.05)} initial="hidden" animate="show">
            {used.map((f) => (
              <motion.li key={f.id} variants={rise}>
                <FactRow f={f} />
              </motion.li>
            ))}
          </motion.ul>
        </div>
      )}
    </motion.div>
  );
}

function FactChip({ f }: { f: ReportFact }) {
  const { open } = useLens();
  const label = `${f.label}: ${f.value}${f.unit ? ` ${f.unit}` : ""}`;
  if (!f.node) return null;
  return (
    <button type="button" onClick={() => open(f.node!)} title={label} aria-label={label} className="mx-0.5 inline-grid h-5 w-5 place-items-center rounded border border-accent/30 bg-accent/5 align-[-3px] text-accent transition hover:bg-accent/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60">
      <ScanSearch className="h-3 w-3" aria-hidden />
    </button>
  );
}

function FactRow({ f }: { f: ReportFact }) {
  const { open } = useLens();
  const numeric = /^-?[\d,]+(\.\d+)?$/.test(f.value);
  const body = numeric ? (
    <>
      <span className="min-w-0 flex-1 text-[12px] text-ink2">{f.label}</span>
      <span className="num shrink-0 font-mono text-[13px] font-medium text-ink">
        {f.value}
        {f.unit && f.unit !== "-" ? <span className="ml-1 font-sans text-[10px] text-muted">{f.unit}</span> : null}
      </span>
      {f.node && <ScanSearch className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />}
    </>
  ) : (
    // words, not a figure ("EU default for India + 2026 mark-up"): under its label, full width
    <span className="min-w-0 flex-1">
      <span className="block text-[12px] text-ink2">{f.label}</span>
      <span className="block text-[13px] font-medium text-ink">{f.value}</span>
    </span>
  );
  return f.node ? (
    <button type="button" onClick={() => open(f.node!)} className="flex w-full items-center gap-3 px-3 py-2 text-left transition hover:bg-sunk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/60">
      {body}
    </button>
  ) : (
    <div className="flex items-center gap-3 px-3 py-2">{body}</div>
  );
}

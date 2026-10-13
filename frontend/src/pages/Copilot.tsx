import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { BookOpen, Loader2, MessageCircleQuestion, SendHorizonal, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { EASE, rise, stagger } from "@/lib/motion";

interface Turn { q: string; a?: any; err?: string }

export default function Copilot() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const examples = useQuery({ queryKey: ["examples"], queryFn: api.examples, staleTime: Infinity });
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState(params.get("q") ?? "");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setQ("");
    setTurns((xs) => [...xs, { q: text }]);
    try {
      const a = await api.ask(text, i18n.language);
      setTurns((xs) => xs.map((x, i) => (i === xs.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      setTurns((xs) => xs.map((x, i) => (i === xs.length - 1 ? { ...x, err: (e as Error).message } : x)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col px-4 py-10 sm:px-6">
      <span className="chip w-fit">EC Guidance No. 1, 2, 3, 4, 5d</span>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{t("copilot.title")}</h1>
      <p className="mt-2 text-ink2">{t("copilot.lead")}</p>

      <div className="mt-6">
        <div className="mb-2 text-[12px] font-semibold text-muted">{t("copilot.examples")}:</div>
        <motion.div className="flex flex-wrap gap-2" variants={stagger(0.05, 0.1)} initial="hidden" animate={examples.data ? "show" : "hidden"}>
          {examples.data?.map((e) => (
            <motion.button key={e} variants={rise} className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl border border-line bg-surface px-3 text-left text-[13px] text-ink2 shadow-card transition hover:-translate-y-0.5 hover:border-accent/40 hover:text-accent disabled:opacity-50" onClick={() => ask(e)} disabled={busy}>
              <MessageCircleQuestion className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
              {e}
            </motion.button>
          ))}
        </motion.div>
      </div>

      <div className="mt-6 space-y-6" aria-live="polite">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-3">
            <motion.div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[14px] text-page" initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.3, ease: EASE }}>
              {turn.q}
            </motion.div>
            {!turn.a && !turn.err && (
              <motion.div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3 text-[13px] text-muted shadow-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}>
                <span className="flex gap-1" aria-hidden>
                  {[0, 1, 2].map((d) => (
                    <motion.span key={d} className="h-1.5 w-1.5 rounded-full bg-accent" animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }} transition={{ duration: 1, repeat: Infinity, delay: d * 0.15 }} />
                  ))}
                </span>
                {t("copilot.thinking")}
              </motion.div>
            )}
            {turn.err && <p className="rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{turn.err}</p>}
            {turn.a && <Answer a={turn.a} />}
          </div>
        ))}
        <div ref={end} />
      </div>

      <form
        className="sticky bottom-4 mt-8 flex gap-2 rounded-2xl border border-line bg-surface p-2 shadow-lift"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(q);
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("copilot.placeholder")} className="min-h-[44px] min-w-0 flex-1 bg-transparent px-3 text-[15px] focus-visible:outline-none" aria-label={t("copilot.placeholder")} maxLength={500} />
        <button className="btn-primary" disabled={busy || !q.trim()} aria-label={t("copilot.ask")}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />} <span className="hidden sm:inline">{t("copilot.ask")}</span>
        </button>
      </form>
    </div>
  );
}

function Answer({ a }: { a: any }) {
  const { t } = useTranslation();
  return (
    <motion.div className="card p-4 sm:p-5" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
      {a.answer ? (
        <div className="flex gap-3">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{a.answer}</p>
        </div>
      ) : (
        <p className="text-[13px] text-muted">{t("copilot.retrieval")}</p>
      )}
      {a.citations?.length > 0 && (
        <motion.div className="mt-3 flex flex-wrap gap-1.5" variants={stagger(0.06, 0.2)} initial="hidden" animate="show">
          {a.citations.map((c: any) => (
            <motion.span key={`${c.doc}${c.page}`} variants={rise} className="chip border-accent/30 bg-accent/5 text-accent">
              <BookOpen className="h-3 w-3" /> {c.doc}, {t("copilot.page")} {c.page}
            </motion.span>
          ))}
        </motion.div>
      )}
      {a.passages?.length > 0 && (
        <details className="mt-4" open={!a.answer}>
          <summary className="cursor-pointer text-[12px] font-semibold text-ink2">{t("copilot.passages")}</summary>
          <ul className="mt-2 space-y-2">
            {a.passages.map((p: any) => (
              <li key={`${p.doc}${p.page}`} className="rounded-xl border border-line bg-sunk p-3">
                <div className="mb-1 text-[11px] font-semibold text-muted">
                  {p.doc} · {t("copilot.page")} {p.page}
                </div>
                <p className="text-[13px] leading-relaxed text-ink2">“{p.snippet}”</p>
              </li>
            ))}
          </ul>
        </details>
      )}
      {a.model && <div className="mt-3 font-mono text-[11px] text-muted">{a.model} · grounded on retrieved pages</div>}
    </motion.div>
  );
}

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Loader2, SendHorizonal, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

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

      <div className="mt-6 flex flex-wrap gap-2">
        <span className="text-[12px] font-semibold text-muted">{t("copilot.examples")}:</span>
        {examples.data?.map((e) => (
          <button key={e} className="chip min-h-[32px] px-3 text-[12px] hover:border-accent/40 hover:text-accent" onClick={() => ask(e)} disabled={busy}>
            {e}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-6" aria-live="polite">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-3">
            <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[14px] text-page">{turn.q}</div>
            {!turn.a && !turn.err && <Loader2 className="h-5 w-5 animate-spin text-muted" />}
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
        <button className="btn-primary" disabled={busy || !q.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />} <span className="hidden sm:inline">{t("copilot.ask")}</span>
        </button>
      </form>
    </div>
  );
}

function Answer({ a }: { a: any }) {
  const { t } = useTranslation();
  return (
    <div className="card p-4 sm:p-5">
      {a.answer ? (
        <div className="flex gap-3">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{a.answer}</p>
        </div>
      ) : (
        <p className="text-[13px] text-muted">{t("copilot.retrieval")}</p>
      )}
      {a.citations?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {a.citations.map((c: any) => (
            <span key={`${c.doc}${c.page}`} className="chip border-accent/30 bg-accent/5 text-accent">
              <BookOpen className="h-3 w-3" /> {c.doc}, {t("copilot.page")} {c.page}
            </span>
          ))}
        </div>
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
    </div>
  );
}

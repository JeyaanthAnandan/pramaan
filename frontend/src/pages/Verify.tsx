import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Check, ClipboardCheck, Loader2, Printer, ScanSearch, X } from "lucide-react";
import { api, imageUrl, type SpotCheck, type SpotItem } from "@/lib/api";
import { CropView } from "@/components/DocImage";
import { EASE, Stamp, rise, stagger } from "@/lib/motion";

const BY = "pramaan.verifier";

function savedName(): string {
  try {
    return localStorage.getItem(BY) ?? "";
  } catch {
    return "";
  }
}

/** Verifier spot-check: a risk-based sample of the values behind the result (every value a person
 *  changed, the supplier's data, then production, rod, gas, scrap and exports by weight). Each value
 *  shows exactly where on the photo it was read; the verifier marks it as matching or not, and the
 *  record prints and goes into the verifier pack. */
export default function Verify() {
  const { pid = "" } = useParams();
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["spotcheck", pid], queryFn: () => api.spotcheck(pid) });
  const [by, setBy] = useState(savedName);
  useEffect(() => {
    try {
      localStorage.setItem(BY, by);
    } catch {
      /* ignore */
    }
  }, [by]);
  const d = q.data;
  const s = d?.summary;
  const done = !!s && s.total > 0 && s.checked === s.total;
  const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(i18n.language === "en" ? "en-IN" : i18n.language, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
  const onMarked = (next: SpotCheck) => qc.setQueryData(["spotcheck", pid], next);
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <Link to={`/p/${pid}/report`} className="btn-quiet -ml-3">
          <ArrowLeft className="h-4 w-4" /> {t("verify.back")}
        </Link>
        <button className="btn-ghost ml-auto" onClick={() => window.print()} disabled={!s?.checked}>
          <Printer className="h-4 w-4" /> {t("verify.print")}
        </button>
      </div>
      <motion.header className="mt-6" variants={stagger(0.06)} initial="hidden" animate="show">
        <motion.div variants={rise} className="eyebrow flex items-center gap-1.5"><ClipboardCheck className="h-3.5 w-3.5" aria-hidden /> {t("verify.title")}</motion.div>
        <motion.h1 variants={rise} className="mt-2 text-[28px] font-semibold leading-tight tracking-tight">{t("verify.h1")}</motion.h1>
        <motion.p variants={rise} className="mt-2 max-w-2xl text-[15px] text-ink2">{t("verify.lead", { n: s?.total ?? 12 })}</motion.p>
      </motion.header>

      <div className="sticky top-16 z-10 -mx-4 mt-5 border-b border-line bg-page/90 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-xl sm:border sm:px-4 print:static">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex min-w-0 flex-1 items-center gap-2 text-[13px]">
            <span className="shrink-0 font-medium">{t("verify.by")}</span>
            <input value={by} onChange={(e) => setBy(e.target.value)} placeholder={t("verify.by_ph")} className="min-h-[36px] w-full min-w-0 max-w-xs rounded-lg border border-line2 bg-surface px-2 text-[14px]" maxLength={60} />
          </label>
          {s && <span className="num text-[13px] text-ink2">{t("verify.progress", { done: s.checked, n: s.total })}</span>}
        </div>
        {s && (
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunk" aria-hidden>
            <motion.div className={`h-full rounded-full ${s.differ ? "bg-warn" : "bg-good"}`} initial={false} animate={{ width: `${(s.checked / Math.max(1, s.total)) * 100}%` }} transition={{ duration: 0.4, ease: EASE }} />
          </div>
        )}
      </div>

      {q.isLoading && (
        <div className="mt-5 space-y-3" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton h-36" />)}
        </div>
      )}
      {q.error && <p className="mt-5 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{String((q.error as Error).message)}</p>}

      {d && (
        <ol className="mt-5 space-y-3">
          {d.items.map((it, i) => (
            <Item key={it.id} pid={pid} it={it} n={i + 1} by={by} when={when} onMarked={onMarked} />
          ))}
        </ol>
      )}

      <AnimatePresence>
        {done && s && (
          <motion.section className={`mt-6 rounded-2xl border p-5 ${s.differ ? "border-warn/40 bg-warnbg/60" : "border-good/40 bg-goodbg/60"}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }} aria-live="polite">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold">{t("verify.done_t")}</h2>
              <Stamp tone={s.differ ? "warn" : "good"} className="ml-auto">{s.differ ? t("verify.stamp_differ", { n: s.differ }) : t("verify.stamp_ok")}</Stamp>
            </div>
            <p className="mt-2 text-[14px] text-ink2">
              {t("verify.done_d", { ok: s.match, n: s.total })} {s.differ ? t("verify.differ_d", { n: s.differ }) : ""}
            </p>
            <p className="mt-1 text-[13px] text-muted">{t("verify.signed", { who: s.by || "—", when: when(s.at) })}</p>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}

function Item({ pid, it, n, by, when, onMarked }: { pid: string; it: SpotItem; n: number; by: string; when: (iso?: string | null) => string; onMarked: (d: SpotCheck) => void }) {
  const { t } = useTranslation();
  const [differ, setDiffer] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const aspect = it.width && it.height ? it.width / it.height : 0.8;
  const name = t(`field.${it.field_key}`, { defaultValue: "" }) || it.label || it.field_key;
  async function mark(match: boolean) {
    setBusy(true);
    setErr(null);
    try {
      await api.spotMark(pid, it.id, { match, note: match ? "" : note, by });
      onMarked(await api.spotcheck(pid));
      setDiffer(false);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }
  const m = it.mark;
  return (
    <motion.li className={`card overflow-hidden ${m ? (m.match ? "border-good/40" : "border-warn/50") : ""}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(n * 0.03, 0.3), duration: 0.3, ease: EASE }}>
      <div className="grid gap-4 p-4 sm:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
        <div className="self-start">
          <CropView src={imageUrl(pid, it.doc_id)} box={it.crop_box} alt={`${name}: ${it.doc_title}`} imgAspect={aspect} />
          <div className="mt-1.5 flex items-center gap-1 text-[11px] text-muted"><ScanSearch className="h-3 w-3" aria-hidden /> {it.doc_title}</div>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="num grid h-6 w-6 place-items-center rounded-full bg-sunk text-[11px] font-semibold">{n}</span>
            <span className={`chip ${it.why === "manual" ? "border-warn/40 bg-warnbg text-warnink" : ""}`}>{t(`verify.why_${it.why}`)}</span>
            {it.period && <span className="text-[12px] text-muted">{it.period}</span>}
          </div>
          <h3 className="mt-2 text-[15px] font-semibold">{[name, it.line].filter(Boolean).join(" · ")}</h3>
          <div className="mt-1 font-mono text-[22px] font-semibold tracking-tight">
            {it.value_text}
            {it.unit && <span className="ml-1 text-[14px] font-normal text-muted">{it.unit}</span>}
          </div>
          <p className="mt-1 text-[12px] text-ink2">
            {it.approved_by ? t("verify.approved_by", { who: it.approved_by }) : it.status === "VERIFIED_2R" ? t("verify.two_readers") : t("verify.status_open")}
          </p>
          <div className="mt-3 print:hidden">
            {m ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-1 text-[13px] font-semibold ${m.match ? "text-goodink" : "text-warnink"}`}>
                  {m.match ? <Check className="h-4 w-4" aria-hidden /> : <X className="h-4 w-4" aria-hidden />} {m.match ? t("verify.matches") : t("verify.differs")}
                </span>
                <span className="text-[12px] text-muted">{t("verify.signed", { who: m.by, when: when(m.at) })}</span>
                <button className="btn-quiet min-h-[32px] px-2 text-[12px]" onClick={() => mark(!m.match)} disabled={busy}>{t("verify.change")}</button>
              </div>
            ) : differ ? (
              <div className="space-y-2">
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("verify.note_ph")} rows={2} maxLength={300} className="w-full rounded-lg border border-line2 bg-surface p-2 text-[14px]" aria-label={t("verify.note_ph")} />
                <div className="flex flex-wrap gap-2">
                  <button className="btn min-h-[40px] border border-warn/60 bg-surface text-warnink hover:bg-warnbg" onClick={() => mark(false)} disabled={busy}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <X className="h-4 w-4" aria-hidden />} {t("verify.save_differ")}
                  </button>
                  <button className="btn-ghost min-h-[40px]" onClick={() => setDiffer(false)} disabled={busy}>{t("common.back")}</button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <button className="btn min-h-[40px] border border-good/50 bg-surface text-goodink hover:bg-goodbg" onClick={() => mark(true)} disabled={busy}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Check className="h-4 w-4" aria-hidden />} {t("verify.matches")}
                </button>
                <button className="btn-ghost min-h-[40px]" onClick={() => setDiffer(true)} disabled={busy}>
                  <X className="h-4 w-4" aria-hidden /> {t("verify.differs")}
                </button>
              </div>
            )}
            {m && !m.match && m.note && <p className="mt-1 text-[13px] text-warnink">“{m.note}”</p>}
            {err && <p className="mt-1 text-[12px] text-badink" role="alert">{err}</p>}
          </div>
          {m && <p className="mt-2 hidden text-[13px] print:block">{m.match ? t("verify.matches") : `${t("verify.differs")}: ${m.note}`} · {t("verify.signed", { who: m.by, when: when(m.at) })}</p>}
        </div>
      </div>
    </motion.li>
  );
}

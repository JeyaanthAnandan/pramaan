import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Camera, Check, ExternalLink, FileCheck2, FolderUp, Loader2, Lock, ScanEye, Send, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { api, supplierImageUrl, type SupplierView } from "@/lib/api";
import { EASE, Stamp, rise, stagger } from "@/lib/motion";
import { Logo, LangSwitch } from "@/components/Layout";
import { StatusBadge } from "@/components/Status";

const STEPS = ["sent", "received", "read", "verified"] as const;
const CODES = new Set(["see", "sefa", "product_cn", "verification_ref"]); // figures and codes in mono

function stepOf(v: SupplierView): number {
  if (v.status === "verified") return 3;
  if (v.documents.length && !v.running && v.values.length) return 2; // read; a person checks the rest
  if (v.documents.length) return 1;
  return 0;
}

/** The supplier's side of the Precursor Lever: open the link on a phone, see what is asked and why,
 *  upload the verified statement, and watch two AI readers check it. No account, no plant data. */
export default function Supplier() {
  const { token = "" } = useParams();
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const q = useQuery({
    queryKey: ["supplier", token],
    queryFn: () => api.supplier(token),
    refetchInterval: (s) => (s.state.data && (s.state.data.running || (s.state.data.status === "received" && !s.state.data.failed && !s.state.data.values.length)) ? 1500 : false),
  });
  const v = q.data;

  async function send(fn: () => Promise<unknown>, key: string) {
    setBusy(key);
    setErr(null);
    try {
      await fn();
      await q.refetch();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  const upload = (files: FileList | null) => files?.length && send(() => api.supplierUpload(token, Array.from(files)), "upload");

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
          <Logo />
          <LangSwitch />
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 pb-16 pt-6" id="main">
        {q.isLoading && (
          <div className="space-y-4" aria-busy="true">
            <div className="skeleton h-28" />
            <div className="skeleton h-16" />
            <div className="skeleton h-56" />
          </div>
        )}
        {q.isError && <p className="mt-20 text-center text-muted">{t("buyer.none")}</p>}
        {v && <Request v={v} token={token} busy={busy} err={err} onSample={() => send(() => api.supplierSample(token), "sample")} onPick={() => fileRef.current?.click()} onCamera={() => camRef.current?.click()} />}
        <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
        <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => upload(e.target.files)} />
      </main>
    </div>
  );
}

function Request({ v, token, busy, err, onSample, onPick, onCamera }: { v: SupplierView; token: string; busy: string | null; err: string | null; onSample: () => void; onPick: () => void; onCamera: () => void }) {
  const { t } = useTranslation();
  const r = v.request;
  const step = stepOf(v);
  const waiting = !v.documents.length || v.failed;
  return (
    <motion.div className="space-y-5" variants={stagger(0.08)} initial="hidden" animate="show">
      <motion.section variants={rise} className="card relative overflow-hidden p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">{t("supplier.eyebrow")}</span>
          {r.is_demo && <span className="chip border-warn/40 bg-warnbg text-warnink">{t("supplier.sample_chip")}</span>}
          {v.status === "verified" && <Stamp className="ml-auto">{t("supplier.stamp")}</Stamp>}
        </div>
        <h1 className="mt-2 font-display text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{t("supplier.title", { company: r.company })}</h1>
        <p className="mt-2 text-[15px] text-ink2">{t("supplier.lead", { precursor: r.precursor, cn: r.precursor_cn, product: r.product, product_cn: r.product_cn })}</p>
      </motion.section>

      <motion.section variants={rise} aria-label={t("supplier.progress")}>
        <Progress step={step} running={v.running} />
      </motion.section>

      {v.status === "verified" && (
        <motion.section variants={rise} className="flex items-start gap-3 rounded-2xl border border-good/40 bg-goodbg px-4 py-3 text-goodink" role="status">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
          <p className="text-[14px]"><b>{t("supplier.done_t")}</b> {t("supplier.done", { company: r.company, product: r.product })}</p>
        </motion.section>
      )}

      {waiting && (
        <motion.section variants={rise} className="card p-5 sm:p-6">
          <h2 className="font-semibold">{t("supplier.why_t")}</h2>
          <p className="mt-1 text-[14px] text-ink2">{t("supplier.why")}</p>
          <h2 className="mt-5 font-semibold">{t("supplier.need_t")}</h2>
          <ol className="mt-2 space-y-2 text-[14px]">
            {(["see", "ver", "sefa", "extra"] as const).map((k, i) => (
              <li key={k} className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sunk font-mono text-[12px] text-ink2">{i + 1}</span>
                <span>{t(`supplier.need_${k}`)}</span>
              </li>
            ))}
          </ol>
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink2">
            <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden /> {t("supplier.need_note")}
          </p>

          <div className="mt-5 rounded-2xl border-2 border-dashed border-line2 p-4 text-center">
            <Upload className="mx-auto h-6 w-6 text-ink2" aria-hidden />
            <p className="mt-1 text-[14px] font-medium">{t("supplier.upload_t")}</p>
            <p className="text-[12px] text-muted">{t("capture.formats")}</p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              <button className="btn-primary" onClick={onCamera} disabled={!!busy}>
                <Camera className="h-4 w-4" /> {t("capture.camera")}
              </button>
              <button className="btn-ghost" onClick={onPick} disabled={!!busy}>
                {busy === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FolderUp className="h-4 w-4" />} {t("capture.choose")}
              </button>
            </div>
            {v.sample_available && (
              <div className="mt-4 border-t border-line pt-4">
                <button className="btn-ghost glint" onClick={onSample} disabled={!!busy}>
                  {busy === "sample" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-accent" />} {t("supplier.sample", { supplier: r.supplier })}
                </button>
                <p className="mt-1.5 text-[12px] text-muted">{t("supplier.sample_d")}</p>
              </div>
            )}
          </div>
          {v.failed && <p className="mt-3 rounded-xl border border-warn/40 bg-warnbg px-3 py-2 text-[13px] text-warnink">{t("supplier.failed", { company: r.company })}</p>}
          {err && <p className="mt-3 rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
        </motion.section>
      )}

      {v.values.length > 0 && <ReadBack v={v} token={token} />}

      <motion.p variants={rise} className="flex items-start gap-2 px-1 text-[12px] text-muted">
        <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden /> {t("supplier.privacy", { company: r.company })}
      </motion.p>
    </motion.div>
  );
}

/** sent -> received -> read by two readers -> verified; the rail fills as the statement moves along. */
function Progress({ step, running }: { step: number; running: boolean }) {
  const { t } = useTranslation();
  const icons = [Send, Upload, ScanEye, ShieldCheck];
  return (
    <ol className="relative grid grid-cols-4 gap-1">
      <span className="absolute left-[12.5%] right-[12.5%] top-[17px] h-0.5 rounded bg-line2" aria-hidden>
        <motion.span className="block h-full rounded bg-good" initial={false} animate={{ width: `${(step / (STEPS.length - 1)) * 100}%` }} transition={{ duration: 0.6, ease: EASE }} />
      </span>
      {STEPS.map((s, i) => {
        const done = i <= step;
        const active = running && i === step + 1;
        const Icon = icons[i];
        return (
          <li key={s} className="relative flex flex-col items-center gap-1.5 text-center" aria-current={i === step ? "step" : undefined}>
            <motion.span
              className={`relative grid h-9 w-9 place-items-center rounded-full border-2 transition-colors duration-300 ${done ? "border-good bg-good text-white" : active ? "border-accent bg-surface text-accent" : "border-line2 bg-surface text-muted"}`}
              initial={false}
              animate={done ? { scale: [1, 1.15, 1] } : { scale: 1 }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              {active ? <Loader2 className="h-4 w-4 animate-spin" /> : done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
            </motion.span>
            <span className={`text-[11px] leading-tight sm:text-[12px] ${done || active ? "font-medium text-ink" : "text-muted"}`}>{t(`supplier.step_${s}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** What the two readers took from the supplier's own document, value by value. */
function ReadBack({ v, token }: { v: SupplierView; token: string }) {
  const { t } = useTranslation();
  const doc = v.documents[0];
  return (
    <motion.section variants={rise} className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
        <h2 className="flex-1 font-semibold">{t("supplier.read_t")}</h2>
        {doc && (
          <a className="btn-quiet text-[13px]" href={supplierImageUrl(token, doc.id)} target="_blank" rel="noopener noreferrer">
            {t("supplier.view_doc")} <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
      <motion.dl className="divide-y divide-line" variants={stagger(0.07)} initial="hidden" animate="show">
        {v.values.map((x) => (
          <motion.div key={`${x.doc_id}-${x.field_key}`} variants={rise} className="px-5 py-2.5">
            <dt className="text-[12px] text-muted">{t(`supplier.f_${x.field_key}`, { defaultValue: x.label })}</dt>
            <dd className="mt-0.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <span className={`min-w-0 ${CODES.has(x.field_key) ? "font-mono text-[15px]" : "text-[14px]"}`}>
                {x.value_text}
                {x.unit && x.unit !== "text" ? <span className="ml-1 font-sans text-[11px] text-muted">{x.unit}</span> : null}
              </span>
              <StatusBadge status={x.status} size="xs" />
            </dd>
          </motion.div>
        ))}
      </motion.dl>
      <p className="border-t border-line bg-sunk/60 px-5 py-2.5 text-[12px] text-muted">{t("supplier.read_d")}</p>
    </motion.section>
  );
}

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { AlertTriangle, CheckCircle2, FileCheck2, FileX2, History, KeyRound, ShieldCheck, ShieldX, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { rise, stagger } from "@/lib/motion";
import { Logo, LangSwitch } from "@/components/Layout";
import { dateTime } from "@/lib/format";
import { sha256Hex, verifyInBrowser, type Receipt as R, type ReceiptChange } from "@/lib/receipt";

/** /r/:id — anyone holding a Pramaan report checks it: the signature is verified here, in this browser,
 *  a dropped-in file is compared byte for byte with the one issued, and the change log says whether the
 *  project still matches. */
export default function Receipt() {
  const { id = "" } = useParams();
  const { t, i18n } = useTranslation();
  const q = useQuery({ queryKey: ["receipt", id], queryFn: () => api.receipt(id), retry: false });
  const r = q.data;
  const [local, setLocal] = useState<boolean | "unsupported" | null>(null);
  useEffect(() => {
    if (!r?.key.pem) return;
    verifyInBrowser(r.key.pem, r.statement_json, r.signature_raw).then(setLocal, () => setLocal("unsupported"));
  }, [r]);
  const genuine = r ? (local === null || local === "unsupported" ? r.signature_valid : local && r.signature_valid) : false;
  const unknownKey = !!r && !r.key.pem; // signed by a development key that is gone: cannot be checked, which is not "forged"
  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4">
          <Logo />
          <LangSwitch />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <div className="eyebrow">{t("receipt.eyebrow")}</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{t("receipt.title")}</h1>
        <p className="mt-1 font-mono text-[13px] text-muted">{id}</p>
        {q.isLoading && <div className="skeleton mt-6 h-40" aria-busy="true" />}
        {q.isError && <p className="mt-8 rounded-2xl border border-bad/40 bg-badbg p-4 text-[14px] text-badink">{t("receipt.none")}</p>}
        {r && (
          <motion.div className="mt-6 space-y-4" variants={stagger(0.08, 0.05)} initial="hidden" animate="show">
            <motion.section variants={rise} className={`card flex items-start gap-3 p-4 ${genuine ? "border-good/40" : unknownKey ? "border-warn/50" : "border-bad/50"}`} data-testid="receipt-signature">
              {genuine ? <ShieldCheck className="mt-0.5 h-7 w-7 shrink-0 text-good" aria-hidden /> : unknownKey ? <AlertTriangle className="mt-0.5 h-7 w-7 shrink-0 text-warn" aria-hidden /> : <ShieldX className="mt-0.5 h-7 w-7 shrink-0 text-bad" aria-hidden />}
              <div className="min-w-0">
                <div className={`text-lg font-semibold ${genuine ? "text-goodink" : unknownKey ? "text-warnink" : "text-badink"}`}>{genuine ? t("receipt.genuine") : unknownKey ? t("receipt.unknown_key") : t("receipt.forged")}</div>
                <p className="text-[13px] text-ink2">{genuine ? t(local === true ? "receipt.genuine_here" : "receipt.genuine_server") : unknownKey ? t("receipt.unknown_key_sub") : t("receipt.forged_sub")}</p>
                <p className="mt-2 flex flex-wrap items-center gap-1.5 text-[12px] text-muted">
                  <KeyRound className="h-3.5 w-3.5" aria-hidden />
                  {r.key.trusted ? t("receipt.key_kms") : <b className="text-warnink">{t("receipt.key_dev")}</b>}
                  {r.key.fingerprint && <span className="font-mono">· {r.key.fingerprint}</span>}
                </p>
              </div>
            </motion.section>

            {r.statement.kind !== "buyer-link" && <FileCheck files={r.statement.fingerprints.files} kind={r.statement.kind} />}

            <motion.section variants={rise} className="card p-4">
              <Now r={r} />
            </motion.section>

            <motion.section variants={rise} className="card p-4">
              <h2 className="text-base font-semibold">{r.statement.project.company}</h2>
              <dl className="mt-1 grid gap-x-6 gap-y-0.5 text-[13px] sm:grid-cols-2">
                <div><dt className="inline text-muted">{t("receipt.period")}: </dt><dd className="inline">{r.statement.project.period}</dd></div>
                <div><dt className="inline text-muted">{t("receipt.issued")}: </dt><dd className="inline">{dateTime(r.statement.issued_at, i18n.language)}</dd></div>
                <div><dt className="inline text-muted">{t("receipt.kind")}: </dt><dd className="inline">{t(`receipt.kind_${r.statement.kind.replace(/[.-]/g, "_")}`)}</dd></div>
                {r.statement.project.fictional_sample && <div className="text-warnink">{t("receipt.sample")}</div>}
              </dl>
              <table className="mt-3 w-full text-[13px]">
                <thead><tr className="text-left text-[11px] uppercase tracking-wide text-muted"><th className="py-1 font-medium">{t("receipt.product")}</th><th className="py-1 text-right font-medium">SEE t CO2/t</th><th className="py-1 pl-3 font-medium">{t("receipt.declares")}</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {r.statement.headline.lines.map((l) => (
                    <tr key={l.line}><td className="py-1.5">{l.product} <span className="text-muted">· CN {l.cn}</span></td><td className="num py-1.5 text-right font-mono">{l.see_t_co2_per_t}</td><td className="py-1.5 pl-3">{l.buyer_declares_2026}</td></tr>
                  ))}
                </tbody>
              </table>
              {r.statement.headline.buyer_saves_eur_per_year && <p className="mt-2 text-[13px]">{t("receipt.saving")}: <b className="num font-mono">EUR {r.statement.headline.buyer_saves_eur_per_year}</b></p>}
              <Values v={r.statement.values} />
            </motion.section>

            <motion.details variants={rise} className="card p-4">
              <summary className="cursor-pointer text-[13px] font-semibold">{t("receipt.how")}</summary>
              <p className="mt-2 text-[13px] text-ink2">{t("receipt.how_body")}</p>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-sunk p-3 text-[11px] leading-relaxed">openssl dgst -sha256 -verify receipt/public_key.pem -signature receipt/statement.sig receipt/statement.json</pre>
              <div className="mt-3 text-[12px] font-semibold">{t("receipt.signed_text")}</div>
              <pre className="mt-1 max-h-72 overflow-auto rounded-lg bg-sunk p-3 text-[11px] leading-relaxed">{JSON.stringify(r.statement, null, 1)}</pre>
            </motion.details>
          </motion.div>
        )}
      </main>
    </div>
  );
}

function FileCheck({ files, kind }: { files: Record<string, string>; kind: string }) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [res, setRes] = useState<{ name: string; ok: boolean; as?: string } | null>(null);
  const [over, setOver] = useState(false);
  async function check(f: File) {
    const h = await sha256Hex(await f.arrayBuffer());
    const hit = Object.entries(files).find(([, d]) => d === h);
    setRes({ name: f.name, ok: !!hit, as: hit?.[0] });
  }
  return (
    <motion.section variants={rise} className="card p-4">
      <div
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) void check(f);
        }}
        className={`flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed p-4 transition ${over ? "border-accent bg-accent/5" : "border-line2"}`}
        data-testid="receipt-drop"
      >
        <Upload className="h-6 w-6 shrink-0 text-muted" aria-hidden />
        <div>
          <div className="text-[14px] font-semibold">{t(kind === "verifier-pack" ? "receipt.drop_pack" : "receipt.drop")}</div>
          <div className="text-[12px] text-muted">{t("receipt.drop_hint")}</div>
        </div>
        <input ref={input} type="file" className="hidden" onChange={(e) => e.target.files?.[0] && void check(e.target.files[0])} />
      </div>
      {res && (
        <p className={`mt-3 flex items-start gap-2 text-[13px] ${res.ok ? "text-goodink" : "text-badink"}`} role="status" data-testid="receipt-file">
          {res.ok ? <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : <FileX2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
          {res.ok ? t("receipt.file_ok", { name: res.name, as: res.as }) : t("receipt.file_bad", { name: res.name })}
        </p>
      )}
    </motion.section>
  );
}

function Now({ r }: { r: R }) {
  const { t, i18n } = useTranslation();
  if (r.now.project === "deleted") return <p className="text-[13px] text-ink2">{t("receipt.deleted")}</p>;
  const n = r.now;
  const same = n.values_match && n.calculation_matches;
  return (
    <div className="space-y-2 text-[13px]">
      <p className={`flex items-start gap-2 ${same ? "text-goodink" : "text-warnink"}`}>
        {same ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
        <b>{same ? t("receipt.current") : t("receipt.changed")}</b>
      </p>
      {n.changes_since.length > 0 && (
        <ul className="ml-6 list-disc space-y-0.5 text-ink2">
          {n.changes_since.map((c) => (
            <li key={c.seq}>{change(c, t)} <span className="text-muted">· {c.actor} · {dateTime(c.at, i18n.language)}</span></li>
          ))}
        </ul>
      )}
      <p className={`flex items-start gap-2 ${n.log.ok && n.log_matches_receipt ? "text-ink2" : "text-badink"}`}>
        <History className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        {n.log.ok && n.log_matches_receipt ? t("receipt.log_ok", { count: n.log.entries }) : t("receipt.log_bad", { at: n.log.broken_at ?? "?" })}
      </p>
    </div>
  );
}

function change(c: ReceiptChange, t: (k: string, o?: Record<string, unknown>) => string): string {
  const b = (c.before ?? {}) as Record<string, string>;
  const a = (c.after ?? {}) as Record<string, string>;
  if (c.action === "edit") return t("receipt.ch_edit", { from: b.value_text ?? "?", to: a.value_text ?? "?" });
  if (c.action === "approve") return t("receipt.ch_approve", { value: b.value_text ?? "" });
  if (c.action === "spot_check") return t(a.match ? "receipt.ch_spot_ok" : "receipt.ch_spot_bad");
  if (c.action === "values_read") return t("receipt.ch_read", { count: Number(a.values ?? 0) });
  if (c.action === "value_added") return t("receipt.ch_added", { value: a.value_text ?? "" });
  return c.action;
}

function Values({ v }: { v: R["statement"]["values"] }) {
  const { t } = useTranslation();
  const rows: [string, number, string][] = [
    ["receipt.v_two", v.two_readers_agree, "text-goodink"],
    ["receipt.v_approved", v.approved_as_read, "text-ink"],
    ["receipt.v_changed", v.changed_by_hand, v.changed_by_hand ? "text-warnink" : "text-ink"],
    ["receipt.v_review", v.waiting_for_review, v.waiting_for_review ? "text-warnink" : "text-ink"],
  ];
  return (
    <div className="mt-3">
      <div className="eyebrow mb-1">{t("receipt.values", { count: v.total })}</div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {rows.map(([k, n, cls]) => (
          <div key={k} className="rounded-lg border border-line px-2.5 py-1.5">
            <dd className={`num font-mono text-lg font-semibold ${cls}`}>{n}</dd>
            <dt className="text-[11px] leading-tight text-muted">{t(k)}</dt>
          </div>
        ))}
      </dl>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { motion } from "motion/react";
import { ArrowRight, Check, Copy, Download, ExternalLink, FileSignature, Link2, Loader2, MessageCircle, Scale, X } from "lucide-react";
import { api, type ProcessResult, type Result } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, n } from "@/lib/format";
import { EASE, Segmented } from "@/lib/motion";
import { LensNum } from "./EvidenceLens";
import { StatusBadge } from "./Status";
import { useToast } from "./Toast";

const STEPS = ["requested", "received", "verified"] as const;

export function Lever({ p, result, whatIf, onWhatIf }: { p: ProcessResult; result: Result; whatIf: boolean; onWhatIf: (v: boolean) => void }) {
  const { t } = useTranslation();
  const { bundle } = useProject();
  const isDemo = !!bundle?.project.is_demo;
  const tree = result.calc_tree;
  const contrib = Number(tree[`${p.id}.rod.contrib`]?.value ?? 0);
  const share = (contrib / Number(p.see)) * 100;
  const actual = p.precursor.data === "ACTUAL_VERIFIED";
  const wi = result.money.what_if[p.id];
  const b = p.buyer;
  const withSupplier = b.with_supplier_eur_t ?? (wi ? String(Math.min(Number(wi[0].eur_t), Number(b.default_eur_t))) : null);

  if (actual) {
    return (
      <section id={`lever-${p.id}`} className="card flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:px-5">
        <Scale className="hidden h-5 w-5 shrink-0 text-muted sm:block" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">
              {t("lever.title")} <span className="font-normal text-muted">· CN {p.cn_display}</span>
            </h3>
            <StatusBadge status="VERIFIED_2R" label={t("lever.status_actual", { supplier: p.precursor.supplier })} />
          </div>
          <p className="mt-1 text-[13px] text-ink2">
            {t("lever.lead", { precursor: p.precursor.name, share: share.toFixed(0) })} SEE <LensNum node={p.precursor.see_node}>{n(p.precursor.see, 3)}</LensNum> · SEFA{" "}
            <LensNum node={p.precursor.sefa_node}>{n(p.precursor.sefa, 3)}</LensNum> · {p.precursor.route}
          </p>
        </div>
        <RequestStatus processId={p.id} inline />
      </section>
    );
  }

  return (
    <section id={`lever-${p.id}`} className="card overflow-hidden ring-1 ring-accent/30">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
        <Scale className="h-5 w-5 text-accent" aria-hidden />
        <h3 className="font-semibold">{t("lever.title")}</h3>
        <span className="text-sm text-muted">· CN {p.cn_display}</span>
        <span className="ml-auto">
          <StatusBadge status="DEFAULT_USED" label={t("lever.status_default", { supplier: p.precursor.supplier })} />
        </span>
      </div>
      <div className="grid gap-5 p-4 sm:p-5 md:grid-cols-[1fr_auto]">
        <div>
          <p className="text-[15px]">{t("lever.lead", { precursor: p.precursor.name, share: share.toFixed(0) })}</p>
          {/* now -> with the supplier's data, read left to right */}
          <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-stretch gap-2 sm:max-w-xl sm:gap-3">
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lever.see_now")}</div>
              <div className="text-2xl font-semibold"><LensNum node={p.see_node}>{n(p.see, 3)}</LensNum></div>
              <div className="text-[11px] text-muted">t CO2/t</div>
            </div>
            <ArrowRight className="h-4 w-4 self-center text-muted" aria-hidden />
            {wi ? (
              <motion.div className="rounded-xl border border-s3/40 bg-s3/5 p-3" initial={{ opacity: 0, x: -8 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, ease: EASE, delay: 0.15 }}>
                <div className="text-[11px] text-muted">{t("lever.see_whatif")}</div>
                <div className="text-2xl font-semibold"><LensNum node={`whatif.${p.id}.see`}>{n(wi[0].see, 3)}</LensNum></div>
                <div className="text-[11px] text-muted">t CO2/t{isDemo ? " · = EC G2" : ""}</div>
              </motion.div>
            ) : (
              <div className="rounded-xl border border-dashed border-line2 p-3 text-[12px] text-muted">{t("lever.no_whatif")}</div>
            )}
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lever.cost_now")}</div>
              <div className="text-xl font-semibold">
                <LensNum node={b.basis_2026 === "default" ? b.cost_default_node : b.cost_actual_node}>{eur(b.buyer_eur_t)}</LensNum>
                <span className="text-sm font-normal text-muted">/t</span>
              </div>
              <div className="text-[11px] text-muted">{b.basis_2026 === "default" ? t("lever.on_default", { actual: eur(b.actual_eur_t) }) : t("lever.on_actual")}</div>
            </div>
            <ArrowRight className="h-4 w-4 self-center text-muted" aria-hidden />
            {withSupplier ? (
              <motion.div className="rounded-xl border border-s3/40 bg-s3/5 p-3" initial={{ opacity: 0, x: -8 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, ease: EASE, delay: 0.3 }}>
                <div className="text-[11px] text-muted">{t("lever.cost_whatif")}</div>
                <div className="text-xl font-semibold">
                  {eur(withSupplier)}
                  <span className="text-sm font-normal text-muted">/t</span>
                </div>
                {Number(b.supplier_saving_eur_t) > 0 && (
                  <motion.div className="mt-0.5 inline-flex rounded bg-goodbg px-1.5 text-[11px] font-semibold text-goodink" initial={{ scale: 0.6, opacity: 0 }} whileInView={{ scale: 1, opacity: 1 }} viewport={{ once: true }} transition={{ type: "spring", stiffness: 500, damping: 18, delay: 0.6 }}>
                    −{eur(b.supplier_saving_eur_t)} {t("lever.saving")}
                  </motion.div>
                )}
              </motion.div>
            ) : (
              <div />
            )}
          </div>
          {wi && (
            <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-[13px] text-ink2">
              <input type="checkbox" checked={whatIf} onChange={(e) => onWhatIf(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--accent))]" />
              {t("lever.whatif", { supplier: p.precursor.supplier })}
            </label>
          )}
        </div>
        <div className="flex flex-col gap-3 md:w-60">
          <LetterDialogWithRefresh processId={p.id} supplier={p.precursor.supplier} />
          <RequestStatus processId={p.id} />
        </div>
      </div>
    </section>
  );
}

function LetterDialogWithRefresh({ processId, supplier }: { processId: string; supplier: string }) {
  const { refresh } = useProject();
  return <LetterDialog processId={processId} supplier={supplier} onSent={refresh} />;
}

/** requested -> received -> verified: the line fills as the supplier moves along. */
function RequestStatus({ processId, inline = false }: { processId: string; inline?: boolean }) {
  const { t } = useTranslation();
  const { bundle, pid, refresh } = useProject();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const req = bundle?.project.supplier_requests.find((s) => s.process_id === processId);
  const idx = STEPS.indexOf((req?.status ?? "not_requested") as (typeof STEPS)[number]); // -1 = not requested

  async function setStatus(st: string) {
    setBusy(st);
    try {
      await api.patchProject(pid, { supplier_status: { [processId]: st } });
      await refresh();
      toast(`${t("lever.track")}: ${t(`lever.st_${st}`)}`, "info");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={inline ? "shrink-0" : ""}>
      {!inline && <div className="eyebrow mb-1.5">{t("lever.track")}</div>}
      <ol className={inline ? "flex flex-wrap gap-1" : "relative space-y-1"} aria-label={t("lever.track")}>
        {!inline && (
          <span className="absolute bottom-4 left-[17px] top-4 w-px bg-line2" aria-hidden>
            <motion.span className="absolute inset-x-0 top-0 block bg-ink" initial={false} animate={{ height: `${(Math.max(idx, 0) / (STEPS.length - 1)) * 100}%` }} transition={{ duration: 0.45, ease: EASE }} />
          </span>
        )}
        {STEPS.map((st) => {
          const me = STEPS.indexOf(st);
          const on = me <= idx;
          return (
            <li key={st} className="relative">
              <button
                className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-sunk ${on ? "text-ink" : "text-muted"}`}
                onClick={() => setStatus(st)}
                disabled={!!busy}
                aria-pressed={on}
              >
                <span className={`relative grid h-5 w-5 place-items-center rounded-full border text-[10px] transition-colors duration-300 ${on ? "border-ink bg-ink text-page" : "border-line2 bg-surface"}`}>
                  {busy === st ? <Loader2 className="h-3 w-3 animate-spin" /> : on ? <Check className="h-3 w-3 animate-pop" /> : me + 1}
                </span>
                {t(`lever.st_${st}`)}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function LetterDialog({ processId, supplier, onSent, compact = false, attention = false }: { processId: string; supplier: string; onSent: () => Promise<void>; compact?: boolean; attention?: boolean }) {
  const { t } = useTranslation();
  const { pid } = useProject();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [text, setText] = useState<string>("");
  const [link, setLink] = useState<{ token: string; url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  async function load(l: "en" | "hi") {
    setLang(l);
    setBusy(true);
    try {
      const r = await api.letter(pid, processId, l);
      setText(r.text);
      setLink(r.link);
      await onSent();
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { setOpen(o); if (o && !text) void load(lang); }}>
      <Dialog.Trigger asChild>
        <button className={`${compact ? "btn-primary h-9 min-h-0" : "btn-primary w-full"} ${attention ? "glint" : ""}`} data-tour="letter">
          <FileSignature className="h-4 w-4" /> {t("lever.letter")}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px] data-[state=closed]:animate-fadeout data-[state=open]:animate-fadein" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[min(720px,94vw)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-line bg-page shadow-lift focus:outline-none data-[state=closed]:animate-dialogout data-[state=open]:animate-dialogin" aria-describedby={undefined}>
          <div className="flex items-center gap-2 border-b border-line px-4 py-3">
            <Dialog.Title className="flex-1 text-sm font-semibold">{t("lever.letter")} · {supplier}</Dialog.Title>
            <Segmented
              role="toggle"
              size="sm"
              value={lang}
              onChange={(l) => void load(l)}
              options={[
                { value: "en", label: "English" },
                { value: "hi", label: "हिंदी" },
              ]}
            />
            <Dialog.Close className="btn-quiet" aria-label={t("common.close")}>
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/50" tabIndex={0} role="region" aria-label={t("lever.letter")}>
            {busy ? (
              <div className="space-y-2.5" aria-busy="true">
                {[92, 100, 85, 97, 60, 0, 88, 94, 70].map((w, i) => (
                  <div key={i} className="skeleton h-3.5" style={{ width: `${w}%`, opacity: w ? 1 : 0 }} />
                ))}
              </div>
            ) : (
              <motion.pre key={lang} lang={lang} className="whitespace-pre-wrap font-sans text-[14px] leading-relaxed" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }}>
                {text}
              </motion.pre>
            )}
          </div>
          {link && <SupplierLinkRow link={link} supplier={supplier} lang={lang} />}
          <div className="flex gap-2 border-t border-line px-4 py-3">
            <button
              className="btn-ghost"
              onClick={async () => {
                await navigator.clipboard.writeText(text);
                setCopied(true);
                toast(t("lever.copied"));
                setTimeout(() => setCopied(false), 1500);
              }}
              disabled={!text}
            >
              {copied ? <Check className="h-4 w-4 animate-pop text-good" /> : <Copy className="h-4 w-4" />} {copied ? t("lever.copied") : t("lever.copy")}
            </button>
            <a className="btn-ghost" href={`data:text/plain;charset=utf-8,${encodeURIComponent(text)}`} download={`supplier-request-${processId}-${lang}.txt`}>
              <Download className="h-4 w-4" /> {t("lever.download")}
            </a>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** The supplier's upload link: copy it, send it on WhatsApp (how Indian suppliers actually reply), or
 *  on the fictional sample open it yourself and play the supplier. */
function SupplierLinkRow({ link, supplier, lang }: { link: { token: string; url: string }; supplier: string; lang: "en" | "hi" }) {
  const { t, i18n } = useTranslation();
  const { bundle } = useProject();
  const toast = useToast();
  const isDemo = !!bundle?.project.is_demo;
  const company = bundle?.project.company ?? "";
  const wa = `https://wa.me/?text=${encodeURIComponent(i18n.t("lever.wa_text", { lng: lang, supplier, company, url: link.url }))}`;
  return (
    <div className="border-t border-line bg-sunk/60 px-4 py-3">
      <div className="flex items-center gap-2 text-[13px] font-semibold">
        <Link2 className="h-4 w-4 text-accent" aria-hidden /> {t("lever.link_t", { supplier })}
      </div>
      <p className="mt-0.5 text-[12px] text-muted">{t("lever.link_d")}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <input readOnly value={link.url} aria-label={t("lever.link_t", { supplier })} className="input min-w-0 flex-1 basis-56 font-mono text-[12px]" onFocus={(e) => e.currentTarget.select()} />
        <button
          className="btn-ghost"
          onClick={async () => {
            await navigator.clipboard.writeText(link.url);
            toast(t("toast.copied"));
          }}
        >
          <Copy className="h-4 w-4" /> {t("exports.copy")}
        </button>
        <a className="btn-ghost" href={wa} target="_blank" rel="noopener noreferrer">
          <MessageCircle className="h-4 w-4" /> WhatsApp
        </a>
        {isDemo && (
          <a className="btn-primary" href={`/supplier/${link.token}`} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-4 w-4" /> {t("lever.as_supplier")}
          </a>
        )}
      </div>
    </div>
  );
}

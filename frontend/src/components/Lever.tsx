import { useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, Copy, Download, FileSignature, Loader2, Scale, X } from "lucide-react";
import { api, type ProcessResult, type Result } from "@/lib/api";
import { useProject } from "@/lib/project";
import { eur, n } from "@/lib/format";
import { LensNum } from "./EvidenceLens";
import { StatusBadge } from "./Status";

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
      <section id={`lever-${p.id}`} className="card flex scroll-mt-20 flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:px-5">
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
    <section id={`lever-${p.id}`} className="card scroll-mt-20 overflow-hidden ring-1 ring-accent/30">
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
          <div className="mt-4 grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lever.see_now")}</div>
              <div className="text-2xl font-semibold"><LensNum node={p.see_node}>{n(p.see, 3)}</LensNum></div>
              <div className="text-[11px] text-muted">t CO2/t</div>
            </div>
            {wi ? (
              <div className="rounded-xl border border-s3/40 bg-s3/5 p-3">
                <div className="text-[11px] text-muted">{t("lever.see_whatif")}</div>
                <div className="text-2xl font-semibold"><LensNum node={`whatif.${p.id}.see`}>{n(wi[0].see, 3)}</LensNum></div>
                <div className="text-[11px] text-muted">t CO2/t{isDemo ? " · = EC G2" : ""}</div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-line2 p-3 text-[12px] text-muted">{t("lever.no_whatif")}</div>
            )}
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lever.cost_now")}</div>
              <div className="text-xl font-semibold">
                <LensNum node={b.basis_2026 === "default" ? b.cost_default_node : b.cost_actual_node}>{eur(b.buyer_eur_t)}</LensNum>
                <span className="text-sm font-normal text-muted">/t</span>
              </div>
              <div className="text-[11px] text-muted">
                {b.basis_2026 === "default" ? t("lever.on_default", { actual: eur(b.actual_eur_t) }) : t("lever.on_actual")}
              </div>
            </div>
            {withSupplier && (
              <div className="rounded-xl border border-s3/40 bg-s3/5 p-3">
                <div className="text-[11px] text-muted">{t("lever.cost_whatif")}</div>
                <div className="text-xl font-semibold">{eur(withSupplier)}<span className="text-sm font-normal text-muted">/t</span></div>
                {Number(b.supplier_saving_eur_t) > 0 && (
                  <div className="text-[11px] font-semibold text-goodink">−{eur(b.supplier_saving_eur_t)} {t("lever.saving")}</div>
                )}
              </div>
            )}
          </div>
          {wi && (
            <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-[13px] text-ink2">
              <input type="checkbox" checked={whatIf} onChange={(e) => onWhatIf(e.target.checked)} className="h-4 w-4" />
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

function RequestStatus({ processId, inline = false }: { processId: string; inline?: boolean }) {
  const { t } = useTranslation();
  const { bundle, pid, refresh } = useProject();
  const [busy, setBusy] = useState<string | null>(null);
  const req = bundle?.project.supplier_requests.find((s) => s.process_id === processId);
  const idx = STEPS.indexOf((req?.status ?? "not_requested") as (typeof STEPS)[number]); // -1 = not requested

  async function setStatus(st: string) {
    setBusy(st);
    try {
      await api.patchProject(pid, { supplier_status: { [processId]: st } });
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={inline ? "shrink-0" : ""}>
      {!inline && <div className="eyebrow mb-1.5">{t("lever.track")}</div>}
      <ol className={inline ? "flex flex-wrap gap-1" : "space-y-1"} aria-label={t("lever.track")}>
        {STEPS.map((st) => {
          const me = STEPS.indexOf(st);
          return (
            <li key={st}>
              <button
                className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] transition hover:bg-sunk ${me <= idx ? "text-ink" : "text-muted"}`}
                onClick={() => setStatus(st)}
                disabled={!!busy}
                aria-pressed={me <= idx}
              >
                <span className={`grid h-5 w-5 place-items-center rounded-full border text-[10px] ${me <= idx ? "border-ink bg-ink text-page" : "border-line2"}`}>{busy === st ? <Loader2 className="h-3 w-3 animate-spin" /> : me <= idx ? <Check className="h-3 w-3" /> : me + 1}</span>
                {t(`lever.st_${st}`)}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function LetterDialog({ processId, supplier, onSent, compact = false }: { processId: string; supplier: string; onSent: () => Promise<void>; compact?: boolean }) {
  const { t } = useTranslation();
  const { pid } = useProject();
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [text, setText] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  async function load(l: "en" | "hi") {
    setLang(l);
    setBusy(true);
    try {
      const r = await api.letter(pid, processId, l);
      setText(r.text);
      await onSent();
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { setOpen(o); if (o && !text) void load(lang); }}>
      <Dialog.Trigger asChild>
        <button className={compact ? "btn-primary h-9 min-h-0" : "btn-primary w-full"}>
          <FileSignature className="h-4 w-4" /> {t("lever.letter")}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[min(720px,94vw)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-line bg-page shadow-lift focus:outline-none" aria-describedby={undefined}>
          <div className="flex items-center gap-2 border-b border-line px-4 py-3">
            <Dialog.Title className="flex-1 text-sm font-semibold">{t("lever.letter")} · {supplier}</Dialog.Title>
            <div className="flex rounded-lg border border-line p-0.5">
              {(["en", "hi"] as const).map((l) => (
                <button key={l} className={`min-h-[32px] rounded-md px-3 text-[13px] ${lang === l ? "bg-sunk font-semibold text-ink" : "text-muted"}`} onClick={() => load(l)}>
                  {l === "en" ? "English" : "हिंदी"}
                </button>
              ))}
            </div>
            <Dialog.Close className="btn-quiet" aria-label={t("common.close")}>
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto p-5">
            {busy ? (
              <div className="grid h-40 place-items-center"><Loader2 className="h-5 w-5 animate-spin text-muted" /></div>
            ) : (
              <pre lang={lang} className="whitespace-pre-wrap font-sans text-[14px] leading-relaxed">{text}</pre>
            )}
          </div>
          <div className="flex gap-2 border-t border-line px-4 py-3">
            <button
              className="btn-ghost"
              onClick={async () => {
                await navigator.clipboard.writeText(text);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              disabled={!text}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} {copied ? t("lever.copied") : t("lever.copy")}
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

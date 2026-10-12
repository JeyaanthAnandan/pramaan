import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Check, CheckCircle2, Copy, KeyRound, Loader2, PackagePlus, Pencil, Plus, Sparkles, Trash2, XCircle } from "lucide-react";
import { api, ApiError, type CnInfo, type ProcessDef } from "@/lib/api";
import { useProject } from "@/lib/project";
import { passcodeFor } from "@/lib/session";
import { EASE } from "@/lib/motion";
import { StatusBadge } from "./Status";
import { useToast } from "./Toast";

type Draft = Pick<ProcessDef, "name" | "cn" | "precursor_name" | "precursor_cn" | "precursor_supplier"> & { source?: string; rationale?: string; doc_ids?: string[]; _k?: number };
const EMPTY: Draft = { name: "", cn: "", precursor_name: "", precursor_cn: "", precursor_supplier: "" };
let seq = 0;
const keyed = (d: Draft): Draft => ({ ...d, _k: ++seq }); // stable keys so a removed line animates out, not the last one
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Own project set-up: who, which period, which product lines (typed, or proposed by Gemini). */
export function SetupCard() {
  const { t } = useTranslation();
  const { pid, bundle } = useProject();
  if (!bundle || bundle.project.is_demo) return null;
  const p = bundle.project;
  const code = passcodeFor(pid);
  return (
    <section id="setup" className="card scroll-mt-20 overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
        <PackagePlus className="h-5 w-5 text-accent" aria-hidden />
        <h2 className="font-semibold">{t("setup.title")}</h2>
        {p.protected && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-[12px] text-ink2">
            <KeyRound className="h-3.5 w-3.5" aria-hidden /> {t("setup.private")}
          </span>
        )}
      </div>
      <div className="space-y-5 p-4 sm:p-5">
        {code && <Passcode code={code} />}
        <Details />
        <ProductLines />
      </div>
    </section>
  );
}

function Passcode({ code }: { code: string }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-accent/25 bg-accent/5 p-3 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1 text-[13px]">
        <div className="font-semibold">{t("setup.passcode")}</div>
        <div className="text-ink2">{t("setup.passcode_d")}</div>
      </div>
      <div className="flex items-center gap-2">
        <code className="rounded-lg border border-line2 bg-surface px-3 py-1.5 font-mono text-[15px] tracking-wider">{code}</code>
        <button
          className="btn-ghost h-9 min-h-0 px-3"
          onClick={async () => {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            toast(t("toast.copied"));
            setTimeout(() => setCopied(false), 1500);
          }}
          aria-label={t("exports.copy")}
        >
          {copied ? <Check className="h-4 w-4 animate-pop text-good" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function Details() {
  const { t } = useTranslation();
  const { pid, bundle, refresh } = useProject();
  const toast = useToast();
  const p = bundle!.project;
  const countries = useQuery({ queryKey: ["countries"], queryFn: api.countries, staleTime: Infinity });
  const [company, setCompany] = useState(p.company);
  const [city, setCity] = useState(p.city);
  const [country, setCountry] = useState(p.country);
  const [last, setLast] = useState(p.months.length);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dirty = company !== p.company || city !== p.city || country !== p.country || last !== p.months.length;
  async function save() {
    setBusy(true);
    setErr(null);
    try {
      await api.patchProject(pid, { company, city, country, months_to: last });
      await refresh();
      toast(t("toast.saved"));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="grid gap-3 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1">
          <span className="text-ink2">{t("setup.company")}</span>
          <input value={company} onChange={(e) => setCompany(e.target.value)} className="min-h-[40px] rounded-lg border border-line2 bg-page px-2" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-ink2">{t("setup.city")}</span>
          <input value={city} onChange={(e) => setCity(e.target.value)} className="min-h-[40px] rounded-lg border border-line2 bg-page px-2" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-ink2">{t("setup.country")}</span>
          <select value={country} onChange={(e) => setCountry(e.target.value)} className="min-h-[40px] rounded-lg border border-line2 bg-page px-2">
            {(countries.data ?? [p.country]).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-ink2">{t("setup.period")}</span>
          <select value={last} onChange={(e) => setLast(Number(e.target.value))} className="min-h-[40px] rounded-lg border border-line2 bg-page px-2">
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>Jan–{m} {p.year}</option>
            ))}
          </select>
        </label>
      </div>
      {dirty && (
        <button className="btn-primary mt-3 h-9 min-h-0" onClick={save} disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} {t("gaps.save")}
        </button>
      )}
      {err && <p className="mt-2 text-[13px] text-badink">{err}</p>}
    </div>
  );
}

export function ProductLines({ embedded = false }: { embedded?: boolean }) {
  const { t } = useTranslation();
  const { pid, bundle, refresh } = useProject();
  const toast = useToast();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const p = bundle!.project;
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lineErrs, setLineErrs] = useState<Record<string, string[]>>({});
  const live = !!health.data?.models?.gemini_configured;
  const hasInvoices = bundle!.documents.some((d) => d.content_type.startsWith("image/"));

  function edit(lines: Draft[]) {
    setErr(null);
    setLineErrs({});
    setDrafts((lines.length ? lines : [{ ...EMPTY }]).map(keyed));
  }
  async function suggest() {
    setBusy("suggest");
    setErr(null);
    try {
      const r = await api.suggestLines(pid);
      if (!r.lines.length) setErr(r.notes || t("setup.none_found"));
      else edit(r.lines.map((l) => ({ name: l.name, cn: l.cn_display, precursor_name: l.precursor_name, precursor_cn: l.precursor_cn, precursor_supplier: l.precursor_supplier, source: "ai", rationale: l.rationale, doc_ids: l.evidence_docs })));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function save(lines: Draft[], confirm = true) {
    setBusy("save");
    setErr(null);
    setLineErrs({});
    try {
      await api.putLines(pid, lines.map(({ _k, ...l }) => l), confirm);
      setDrafts(null);
      await refresh();
      toast(t("toast.lines_saved"));
    } catch (e) {
      if (e instanceof ApiError && e.detail && typeof e.detail === "object" && "lines" in (e.detail as Record<string, unknown>)) {
        setLineErrs((e.detail as { lines: Record<string, string[]> }).lines);
      }
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  const current: Draft[] = p.processes.map((x) => ({ name: x.name, cn: x.cn_display, precursor_name: x.precursor_name, precursor_cn: x.precursor_cn, precursor_supplier: x.precursor_supplier, source: x.source, rationale: x.rationale, doc_ids: x.evidence_docs }));

  return (
    <div>
      {!embedded && (
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{t("setup.lines")}</h3>
          {p.processes.length > 0 && (
            <StatusBadge status={p.processes_confirmed ? "green" : "amber"} label={p.processes_confirmed ? t("setup.confirmed") : t("setup.unconfirmed")} />
          )}
        </div>
      )}
      {drafts ? (
        <Editor drafts={drafts} setDrafts={setDrafts} errors={lineErrs} country={p.country} onCancel={() => setDrafts(null)} onSave={() => save(drafts)} busy={busy === "save"} />
      ) : p.processes.length ? (
        <div className="space-y-2">
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {p.processes.map((x) => (
              <li key={x.id} className="flex flex-col gap-1 px-3 py-2.5 text-[13px] sm:flex-row sm:items-center sm:gap-4">
                <span className="w-8 shrink-0 font-mono text-muted">{x.id}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">
                    {x.name} <span className="font-normal text-muted">· CN {x.cn_display}</span>
                  </div>
                  <div className="text-ink2">
                    ← {x.precursor_name} (CN {x.precursor_cn.replace(/^(\d{4})(\d{2})(\d{2})$/, "$1 $2 $3")}) · {x.precursor_supplier}
                  </div>
                  {x.rationale && <div className="text-[12px] text-muted">{x.rationale}</div>}
                </div>
                {x.source === "ai" && <span className="chip shrink-0 border-accent/25 bg-accent/5 text-accent"><Sparkles className="h-3 w-3" /> {t("setup.by_ai")}</span>}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            {!p.processes_confirmed && (
              <button className="btn-primary h-9 min-h-0" onClick={() => save(current, true)} disabled={!!busy}>
                {busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} {t("setup.confirm")}
              </button>
            )}
            <button className="btn-ghost h-9 min-h-0" onClick={() => edit(current)} disabled={!!busy}>
              <Pencil className="h-4 w-4" /> {t("gaps.edit")}
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-line2 p-4 text-[13px]">
          <p className="text-ink2">{t("setup.none")}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-primary h-9 min-h-0" onClick={suggest} disabled={!live || !hasInvoices || !!busy} title={!live ? t("setup.needs_live") : !hasInvoices ? t("setup.needs_docs") : undefined}>
              {busy === "suggest" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} {t("setup.suggest")}
            </button>
            <button className="btn-ghost h-9 min-h-0" onClick={() => edit([])} disabled={!!busy}>
              <Plus className="h-4 w-4" /> {t("setup.add_manual")}
            </button>
          </div>
          <p className="mt-2 text-[12px] text-muted">{!live ? t("setup.needs_live") : !hasInvoices ? t("setup.needs_docs") : t("setup.or_run")}</p>
        </div>
      )}
      {err && <p className="mt-2 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-[13px] text-badink">{err}</p>}
    </div>
  );
}

function Editor({ drafts, setDrafts, errors, country, onCancel, onSave, busy }: { drafts: Draft[]; setDrafts: (d: Draft[]) => void; errors: Record<string, string[]>; country: string; onCancel: () => void; onSave: () => void; busy: boolean }) {
  const { t } = useTranslation();
  const set = (i: number, patch: Partial<Draft>) => setDrafts(drafts.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  return (
    <div className="space-y-3">
      <AnimatePresence initial={false}>
      {drafts.map((d, i) => (
        <motion.fieldset key={d._k ?? i} className="rounded-xl border border-line bg-surface p-3" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }} transition={{ duration: 0.25, ease: EASE }}>
          <legend className="flex items-center gap-2 px-1 text-[12px] font-semibold">
            P{i + 1}
            {d.source === "ai" && <span className="chip border-accent/25 bg-accent/5 py-0 text-accent"><Sparkles className="h-3 w-3" /> {t("setup.by_ai")}</span>}
          </legend>
          {d.rationale && <p className="mb-2 text-[12px] text-muted">{d.rationale}</p>}
          <div className="grid gap-3 text-[13px] sm:grid-cols-2">
            <Text label={t("setup.f_name")} value={d.name} onChange={(v) => set(i, { name: v })} placeholder="Stainless hexagon bolts" />
            <CnField label={t("setup.f_cn")} value={d.cn} onChange={(v) => set(i, { cn: v })} country={country} role="good" />
            <Text label={t("setup.f_pre")} value={d.precursor_name} onChange={(v) => set(i, { precursor_name: v })} placeholder="Stainless wire rod" />
            <CnField label={t("setup.f_pre_cn")} value={d.precursor_cn} onChange={(v) => set(i, { precursor_cn: v })} country={country} role="precursor" />
            <Text label={t("setup.f_supplier")} value={d.precursor_supplier} onChange={(v) => set(i, { precursor_supplier: v })} placeholder="Rod mill name" />
          </div>
          {errors[String(i)] && (
            <ul className="mt-2 space-y-0.5 text-[12px] text-badink">
              {errors[String(i)].map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {drafts.length > 1 && (
            <button className="btn-quiet mt-2 h-8 min-h-0 text-[12px]" onClick={() => setDrafts(drafts.filter((_, j) => j !== i))}>
              <Trash2 className="h-3.5 w-3.5" /> {t("setup.remove")}
            </button>
          )}
        </motion.fieldset>
      ))}
      </AnimatePresence>
      <div className="flex flex-wrap gap-2">
        {drafts.length < 6 && (
          <button className="btn-ghost h-9 min-h-0" onClick={() => setDrafts([...drafts, keyed(EMPTY)])}>
            <Plus className="h-4 w-4" /> {t("setup.add_line")}
          </button>
        )}
        <button className="btn-primary h-9 min-h-0" onClick={onSave} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} {t("setup.save_confirm")}
        </button>
        <button className="btn-quiet h-9 min-h-0" onClick={onCancel}>{t("gaps.cancel")}</button>
      </div>
    </div>
  );
}

function Text({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-ink2">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="min-h-[40px] rounded-lg border border-line2 bg-page px-2" />
    </label>
  );
}

/** CN code field: digits are checked against the official refdata as you type; words search the
 *  CBAM iron & steel list by description. */
function CnField({ label, value, onChange, country, role }: { label: string; value: string; onChange: (v: string) => void; country: string; role: "good" | "precursor" }) {
  const { t } = useTranslation();
  const digits = value.replace(/\D/g, "");
  const words = /[a-z]{3,}/i.test(value);
  const [q, setQ] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setQ(value), 300);
    return () => window.clearTimeout(id);
  }, [value]);
  const check = useQuery<CnInfo>({ queryKey: ["cn", digits, country, role], queryFn: () => api.cn(digits, country, role), enabled: !words && digits.length === 8, staleTime: Infinity });
  const search = useQuery({ queryKey: ["cn-search", q, country], queryFn: () => api.cnSearch(q, country), enabled: words && q.length >= 3, staleTime: 60_000 });
  return (
    <div className="flex flex-col gap-1">
      <label className="flex flex-col gap-1">
        <span className="text-ink2">{label}</span>
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={t("setup.cn_hint")} className="num min-h-[40px] rounded-lg border border-line2 bg-page px-2" />
      </label>
      {!words && digits.length === 8 && check.data && (
        <p key={`${digits}-${check.data.ok}`} className={`flex animate-rise items-start gap-1 text-[12px] ${check.data.ok ? "text-goodink" : "text-badink"}`}>
          {check.data.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
          <span>{check.data.ok ? check.data.description : check.data.errors.join(" ")}</span>
        </p>
      )}
      {!words && digits.length > 0 && digits.length !== 8 && <p className="text-[12px] text-muted">{t("setup.cn_digits")}</p>}
      {words && search.data && (
        <ul className="max-h-48 overflow-y-auto rounded-lg border border-line bg-page text-[12px]">
          {search.data.length ? (
            search.data.map((h) => (
              <li key={h.cn}>
                <button className="w-full px-2 py-1.5 text-left hover:bg-sunk" onClick={() => onChange(h.cn_display)}>
                  <span className="num font-semibold">{h.cn_display}</span> · {h.description}
                </button>
              </li>
            ))
          ) : (
            <li className="px-2 py-1.5 text-muted">{t("setup.cn_nohit")}</li>
          )}
        </ul>
      )}
    </div>
  );
}

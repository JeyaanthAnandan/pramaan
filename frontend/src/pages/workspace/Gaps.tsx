import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight, Check, ChevronDown, Loader2, PackagePlus, Pencil, Scale, ScanSearch, UserRound } from "lucide-react";
import { api, imageUrl, type Gap } from "@/lib/api";
import { parseQuantity } from "@/lib/format";
import { useProject } from "@/lib/project";
import { AnimatedNumber, Collapse, EASE, Stamp, rise, stagger, useAfter } from "@/lib/motion";
import { useToast } from "@/components/Toast";
import { DocImage, CropView } from "@/components/DocImage";
import { VoiceAnswer } from "@/components/VoiceAnswer";
import { StatusBadge } from "@/components/Status";
import { useLens } from "@/components/EvidenceLens";
import { ProductLines } from "@/components/Setup";
import { LoadError } from "@/components/ErrorBoundary";

const GROUPS = ["review", "setup", "precursor", "activity", "energy", "exports", "extra", "control"];

function gapText(t: (k: string, o?: Record<string, unknown>) => string, g: Gap, lines: Record<string, string> = {}) {
  const params: Record<string, unknown> = { ...g.params };
  // a value to review is named by what it is and its product line, in the reader's language; the label
  // as printed on the page (Hindi on the sample's scrap log) stays the fallback
  if (g.group === "review" && typeof params.field_key === "string") {
    const name = t(`field.${params.field_key}`, { defaultValue: "" });
    if (name) params.label = [name, g.process ? lines[g.process] : ""].filter(Boolean).join(" · ");
  }
  if (Array.isArray(params.missing)) params.missing = (params.missing as string[]).join(", ");
  if (Array.isArray(params.quarters)) params.quarters = (params.quarters as string[]).join(", ");
  const base = `gaps.kinds.${g.kind}`;
  const title = t(`${base}.t`, params);
  let q: string;
  if (g.kind === "precursor_see" || g.kind === "precursor_sefa") q = t(`${base}.${g.params.data === "ACTUAL_VERIFIED" || g.status === "green" ? "q_actual" : "q_default"}`, params);
  else q = t(`${base}.q`, params);
  return { title, q };
}

function useGapText() {
  const { t } = useTranslation();
  const { bundle } = useProject();
  const lines = useMemo(() => Object.fromEntries((bundle?.project.processes ?? []).map((p) => [p.id, p.name])), [bundle]);
  return (g: Gap) => gapText(t, g, lines);
}

export default function Gaps() {
  const { t } = useTranslation();
  const { pid, result } = useProject();
  if (!result) return <NoResult />;
  const gaps = result.gaps;
  const counts = { red: 0, amber: 0, green: 0 } as Record<string, number>;
  gaps.forEach((g) => (counts[g.status] = (counts[g.status] ?? 0) + 1));
  const reviews = gaps.filter((g) => g.group === "review");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-0 flex-[1_1_18rem]">
          <h2 className="text-2xl font-semibold tracking-tight">{t("gaps.title")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink2">{t("gaps.lead")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["red", "amber", "green"] as const).map((k) => (
            <StatusBadge key={k} status={k} label={<><AnimatedNumber value={counts[k] ?? 0} format={(v) => v.toFixed(0)} /> · {t(`status.${k}`)}</>} />
          ))}
        </div>
      </div>

      <section>
        <h3 className="eyebrow mb-2">{t("gaps.group_review")}</h3>
        <AnimatePresence initial={false}>
          {reviews.map((g) => (
            <motion.div key={g.id} className="overflow-hidden" exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.4, ease: EASE }}>
              <div className="pb-4">
                <ReviewCard g={g} />
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {!reviews.length && (
          <motion.p className="flex items-center gap-2 rounded-xl border border-good/30 bg-goodbg px-4 py-3 text-sm text-goodink" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE, delay: 0.15 }}>
            <Check className="h-4 w-4 animate-pop" /> {t("gaps.all_clear")}
          </motion.p>
        )}
      </section>

      <motion.div className="space-y-6" variants={stagger(0.06, 0.1)} initial="hidden" animate="show">
        {GROUPS.filter((gr) => gr !== "review").map((gr) => (
          <GapGroup key={gr} group={gr} items={gaps.filter((g) => g.group === gr)} />
        ))}
      </motion.div>
      <div className="flex justify-end">
        <Link to={`/p/${pid}/report`} className="btn-primary nudge">
          {t("steps.report")} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function SetupGap({ g }: { g: Gap }) {
  const { t } = useTranslation();
  const gtext = useGapText();
  const { pid } = useProject();
  const { title, q } = gtext(g);
  return (
    <motion.section variants={rise}>
      <h3 className="eyebrow mb-2">{t("gaps.group_setup")}</h3>
      <div className={`card p-4 sm:p-5 ${g.status === "red" ? "border-bad/40" : "border-warn/50"}`}>
        <div className="flex flex-wrap items-start gap-3">
          <PackagePlus className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={g.status} />
              <h4 className="font-semibold">{title}</h4>
            </div>
            <p className="mt-1 text-[13px] text-ink2">{q}</p>
          </div>
          <Link to={`/p/${pid}/capture#setup`} className="btn-ghost h-9 min-h-0">
            {t("next.setup_cta")}
          </Link>
        </div>
        <div className="mt-3">
          <ProductLines embedded />
        </div>
      </div>
    </motion.section>
  );
}

function GapGroup({ group, items }: { group: string; items: Gap[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  if (group === "setup") return <SetupGap g={items[0]} />;
  const attention = items.filter((g) => g.status === "red" || g.status === "amber");
  const rest = items.filter((g) => g.status !== "red" && g.status !== "amber");
  const toggle = attention.length > 0 && rest.length > 0;
  return (
    <motion.section variants={rise}>
      <h3 className="eyebrow mb-2">{t(`gaps.group_${group}`)}</h3>
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
        <ul>
          {attention.map((g) => (
            <GapRow key={g.id} g={g} />
          ))}
          {!toggle && rest.map((g) => <GapRow key={g.id} g={g} />)}
        </ul>
        {toggle && (
          <>
            <Collapse open={open}>
              <ul>
                {rest.map((g) => (
                  <GapRow key={g.id} g={g} />
                ))}
              </ul>
            </Collapse>
            <button className="flex min-h-[44px] w-full items-center gap-2 border-t border-line px-4 text-[13px] text-ink2 transition-colors hover:bg-sunk" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
              <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
              {open ? t("gaps.hide_ok") : t("gaps.show_ok", { count: rest.length })}
            </button>
          </>
        )}
      </div>
    </motion.section>
  );
}

function GapRow({ g }: { g: Gap }) {
  const { t } = useTranslation();
  const gtext = useGapText();
  const { open } = useLens();
  const { title, q } = gtext(g);
  return (
    <li className="flex flex-col gap-2 border-t border-line px-4 py-3 transition-colors first:border-t-0 hover:bg-sunk/40 sm:flex-row sm:items-center sm:gap-4">
      <div className="w-36 shrink-0">
        <StatusBadge status={g.status} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{title}</div>
        <div className="text-[13px] leading-relaxed text-ink2">{q}</div>
        {g.lever && <div className="mt-1 text-[12px] font-semibold text-accent">{t("lever.title")} →</div>}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {["al", "rod_mass", "scrap"].includes(g.kind) && g.process && <VoiceAnswer kind={g.kind} process={g.process} missing={(g.params.missing as string[]) ?? []} />}
        {g.ask && (
          <span className="chip">
            <UserRound className="h-3 w-3" /> {t(`gaps.ask.${g.ask}`)}
          </span>
        )}
        {g.node && (
          <button className="btn-quiet" onClick={() => open(g.node!)} aria-label="Open in Evidence Lens">
            <ScanSearch className="h-4 w-4" />
          </button>
        )}
      </div>
    </li>
  );
}

function ReviewCard({ g }: { g: Gap }) {
  const { t, i18n } = useTranslation();
  const gtext = useGapText();
  const { pid, evById, docs, refresh } = useProject();
  const toast = useToast();
  const reduce = useReducedMotion();
  const ev = evById[g.evidence_ids[0]];
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(ev?.value_text ?? "");
  const [stamped, setStamped] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // the story in order: reader 1 read the page, then reader 2 read only the crop, then they disagree
  const second = useAfter(420, [ev?.id]);
  const verdict = useAfter(900, [ev?.id]);
  if (!ev) return null;
  const doc = docs[ev.doc_id];
  const aspect = doc?.width && doc?.height ? doc.width / doc.height : 0.75;
  const { title, q } = gtext(g);
  const supports = g.params.balance?.supports as "first" | "second" | undefined;
  const crossed = ev.second_reading?.corrected_from; // a crossed-out figure next to the value
  const handFix = !!crossed && !!ev.second_reading?.agrees; // both read the same, but a person confirms a hand correction
  async function act(action: "approve" | "edit", value?: string) {
    // an edit must be a number the engine can use: "15,4" is 15.4 (a decimal comma), never 154
    const num = action === "edit" ? parseQuantity(value ?? "", i18n.language) : null;
    if (action === "edit" && num === null) {
      setErr(t("gaps.not_a_number"));
      return;
    }
    setErr(null);
    setBusy(value ?? action);
    try {
      await api.patchEvidence(pid, ev.id, action === "edit" ? { action, value_text: value!.trim(), value_num: num!, user: "Owner (demo)" } : { action, user: "Owner (demo)" });
      const v = action === "edit" ? value!.trim() : ev.value_text;
      setStamped(v);
      toast(t("toast.approved", { value: v }));
      if (!reduce) await new Promise((r) => window.setTimeout(r, 750)); // let the stamp land before the card folds away
      setEditing(false);
      await refresh();
    } catch (e) {
      setErr(t("common.failed", { msg: (e as Error).message })); // the form stays open with what was typed
    } finally {
      setBusy(null);
    }
  }
  const ring = (which: "first" | "second") => (verdict && supports === which ? "ring-2 ring-good/60 ring-offset-2 ring-offset-surface" : "");
  return (
    <div className="card relative overflow-hidden border-warn/50">
      <div className="grid gap-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="border-b border-line p-3 md:border-b-0 md:border-r">
          {doc?.content_type.startsWith("audio/") ? (
            <div className="flex h-full flex-col justify-center gap-3 rounded-xl bg-sunk p-4">
              <div className="eyebrow">{t("doctype.voice_note", { defaultValue: "Voice note" })}</div>
              <audio controls src={imageUrl(pid, ev.doc_id)} className="w-full" />
              <p className="whitespace-pre-wrap text-[13px] text-ink2">{ev.notes}</p>
            </div>
          ) : (
            <DocImage src={imageUrl(pid, ev.doc_id)} box={ev.box_2d} alt={doc?.title ?? ev.doc_id} aspect={aspect} tone="warn" label={doc?.doc_type ? t(`doctype.${doc.doc_type}`) : undefined} />
          )}
        </div>
        <div className="flex flex-col p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <StatusBadge status="NEEDS_REVIEW" />
            <span className="text-[12px] text-muted">{ev.period}</span>
          </div>
          <h4 className="mt-2 text-lg font-semibold">{title}</h4>
          <p className="mt-1 text-sm text-ink2">{q}</p>
          <div className="relative mt-4 grid grid-cols-2 gap-x-9 gap-y-3" data-tour="review">
            <div className={`rounded-xl border border-line bg-surface p-3 transition-shadow duration-500 ${ring("first")}`}>
              <div className="text-[11px] text-muted">{t("gaps.reader1")}</div>
              <div className="font-mono text-2xl">{ev.value_text}</div>
              <div className="truncate text-[11px] text-muted">{ev.extractor_model}</div>
            </div>
            <motion.div className={`rounded-xl border border-warn/50 bg-warnbg p-3 transition-shadow duration-500 ${ring("second")}`} initial={false} animate={second ? { opacity: 1, x: 0 } : { opacity: 0, x: -10 }} transition={{ duration: 0.35, ease: EASE }}>
              <div className="text-[11px] text-ink2">{t("gaps.reader2")}</div>
              <div className="font-mono text-2xl">{ev.second_reading?.reading_value ?? "—"}</div>
              {crossed && (
                <div className="mt-0.5 flex items-center gap-1 text-[12px] font-medium text-warnink">
                  <Pencil className="h-3 w-3 shrink-0" aria-hidden /> {t("gaps.crossed_out", { value: crossed })}
                </div>
              )}
              <div className="truncate text-[11px] text-ink2">{ev.second_reading?.model}</div>
            </motion.div>
            <AnimatePresence>
              {verdict && (
                <motion.span
                  key="neq"
                  className="absolute left-1/2 top-1/2 grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-warn/60 bg-surface font-mono text-[15px] font-semibold text-warnink shadow-card"
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 520, damping: 20 }}
                  role="img"
                  aria-label={handFix ? t("gaps.corrected") : t("lens.disagree")}
                >
                  {handFix ? <Pencil className="h-3.5 w-3.5" /> : "≠"}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          {g.params.balance && (
            <motion.div className="mt-3 flex items-start gap-2 rounded-xl border border-line bg-sunk px-3 py-2 text-[13px]" initial={false} animate={verdict ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }} transition={{ duration: 0.35, ease: EASE }}>
              <Scale className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
              <span>
                <b>{t("gaps.balance_t", { defaultValue: "Mass-balance check" })}</b> ({ev.period}): {g.params.balance.formula} = <b className="num">{g.params.balance.implied} t</b>
                {supports && <span className="text-goodink"> → {t(supports === "first" ? "gaps.supports_1" : "gaps.supports_2")}</span>}
              </span>
            </motion.div>
          )}
          {ev.second_reading?.crop_box && (
            <div className="mt-3 max-w-[340px]">
              <CropView src={imageUrl(pid, ev.doc_id)} box={ev.second_reading.crop_box} alt="crop seen by reader 2" imgAspect={aspect} />
            </div>
          )}
          <div className="mt-auto flex flex-wrap gap-2 pt-4">
            {!editing ? (
              <>
                <button className="btn-primary" onClick={() => act("approve")} disabled={!!busy}>
                  {busy === "approve" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} {t("gaps.approve_value", { value: ev.value_text })}
                </button>
                {ev.second_reading?.reading_value && ev.second_reading.reading_value !== ev.value_text && (
                  <button className="btn-ghost" onClick={() => act("edit", ev.second_reading!.reading_value!)} disabled={!!busy}>
                    {busy === ev.second_reading.reading_value && <Loader2 className="h-4 w-4 animate-spin" />}
                    {t("gaps.approve_value", { value: ev.second_reading.reading_value })}
                  </button>
                )}
                <button className="btn-quiet" onClick={() => setEditing(true)}>
                  <Pencil className="h-4 w-4" /> {t("gaps.edit")}
                </button>
              </>
            ) : (
              <form
                className="flex w-full gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void act("edit", val);
                }}
              >
                <input value={val} onChange={(e) => (setVal(e.target.value), setErr(null))} inputMode="decimal" className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line2 bg-surface px-3 font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" aria-label={t("gaps.edit")} aria-invalid={!!err} aria-describedby={err ? `err-${ev.id}` : undefined} />
                <button className="btn-primary" disabled={!!busy}>{t("gaps.save")}</button>
                <button type="button" className="btn-quiet" onClick={() => (setEditing(false), setErr(null))}>{t("gaps.cancel")}</button>
              </form>
            )}
            {err && (
              <p id={`err-${ev.id}`} role="alert" className="w-full text-[13px] text-badink">
                {err}
              </p>
            )}
          </div>
        </div>
      </div>
      <AnimatePresence>
        {stamped && (
          <motion.div key="stamp" className="pointer-events-none absolute inset-0 grid place-items-center bg-surface/45 backdrop-blur-[1px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
            <Stamp tone="good" className="px-5 py-2 text-[20px]">
              <Check className="h-5 w-5" aria-hidden /> {t("status.APPROVED")} · {stamped}
            </Stamp>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function NoResult() {
  const { t } = useTranslation();
  const { pid, bundle, error, refresh } = useProject();
  // the project has a report that did not load (a server hiccup): retry it, never suggest a new run
  if (bundle?.has_result) return error ? <LoadError error={error} onRetry={() => void refresh()} /> : <div className="skeleton mx-auto h-40 max-w-lg" aria-busy="true" />;
  return (
    <div className="card mx-auto max-w-lg p-8 text-center">
      <p className="text-sm text-ink2">{t("timeline.empty")}</p>
      <Link to={`/p/${pid}/capture`} className="btn-primary mt-4">
        {t("capture.run")}
      </Link>
    </div>
  );
}

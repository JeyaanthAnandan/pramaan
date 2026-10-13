import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, BookMarked, Check, ChevronRight, ExternalLink, FileImage, FlaskConical, ScanSearch, Sigma, Sparkles, UserCheck, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { imageUrl, type CalcNode } from "@/lib/api";
import { useProject } from "@/lib/project";
import { EASE, rise, stagger, useAfter } from "@/lib/motion";
import { DocImage, CropView } from "./DocImage";
import { StatusBadge, toneOf } from "./Status";
import { when } from "@/lib/format";

interface LensCtx {
  open: (nodeId: string) => void;
}
const Ctx = createContext<LensCtx>({ open: () => {} });
export const useLens = () => useContext(Ctx);

export function LensProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [dir, setDir] = useState(1); // +1 drilling down, -1 going back: the panel slides that way
  const open = useCallback((id: string) => {
    setDir(1);
    setStack([id]);
    setIsOpen(true);
  }, []);
  const value = useMemo(() => ({ open }), [open]);
  // "Explain in plain words" hands the number to the Ask panel: the lens steps aside
  useEffect(() => {
    const f = () => setIsOpen(false);
    window.addEventListener("pramaan:ask", f);
    return () => window.removeEventListener("pramaan:ask", f);
  }, []);
  return (
    <Ctx.Provider value={value}>
      {children}
      <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px] data-[state=closed]:animate-fadeout data-[state=open]:animate-fadein" />
          <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] flex-col border-l border-line bg-page shadow-lift focus:outline-none data-[state=closed]:animate-sheetout data-[state=open]:animate-sheet" aria-describedby={undefined}>
            {stack.length > 0 && (
              <LensBody
                stack={stack}
                dir={dir}
                push={(id) => {
                  setDir(1);
                  setStack((s) => [...s, id]);
                }}
                jump={(i) => {
                  setDir(-1);
                  setStack((s) => s.slice(0, i + 1));
                }}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </Ctx.Provider>
  );
}

function LensBody({ stack, dir, push, jump }: { stack: string[]; dir: number; push: (id: string) => void; jump: (i: number) => void }) {
  const { t } = useTranslation();
  const { result } = useProject();
  const nodeId = stack[stack.length - 1];
  const depth = stack.length;
  const node = result?.calc_tree[nodeId];
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [nodeId]);
  return (
    <>
      <header className="border-b border-line bg-surface px-4 py-3">
        <div className="flex items-center gap-2">
          {depth > 1 ? (
            <button className="btn-quiet -ml-2" onClick={() => jump(depth - 2)} aria-label={t("lens.back")}>
              <ArrowLeft className="h-4 w-4" />
            </button>
          ) : (
            <ScanSearch className="h-5 w-5 text-accent" aria-hidden />
          )}
          <Dialog.Title className="flex-1 text-sm font-semibold">{t("lens.title")}</Dialog.Title>
          <Dialog.Close className="btn-quiet -mr-2" aria-label={t("common.close")}>
            <X className="h-4 w-4" />
          </Dialog.Close>
        </div>
        {depth > 1 && (
          <nav aria-label={t("lens.path")} className="mt-1.5">
            <ol className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11px] text-muted">
              {stack.map((id, i) => {
                const label = result?.calc_tree[id]?.label ?? id;
                const last = i === stack.length - 1;
                return (
                  <li key={`${id}-${i}`} className="flex min-w-0 items-center gap-1">
                    {i > 0 && <ChevronRight className="h-3 w-3 shrink-0" aria-hidden />}
                    {last ? (
                      <span className="max-w-[180px] truncate font-medium text-ink2" aria-current="page" title={label}>{label}</span>
                    ) : (
                      <button className="max-w-[140px] truncate rounded hover:text-accent hover:underline" onClick={() => jump(i)} title={label}>{label}</button>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>
        )}
      </header>
      <div ref={scroller} className="flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-5">
        <AnimatePresence mode="wait" initial={false} custom={dir}>
          <motion.div
            key={`${nodeId}-${depth}`}
            custom={dir}
            variants={{
              enter: (d: number) => ({ opacity: 0, x: d * 28 }),
              center: { opacity: 1, x: 0, transition: { duration: 0.24, ease: EASE } },
              exit: (d: number) => ({ opacity: 0, x: d * -28, transition: { duration: 0.12, ease: "easeIn" } }),
            }}
            initial="enter"
            animate="center"
            exit="exit"
          >
            {node ? <NodeView node={node} push={push} /> : <p className="text-sm text-muted">—</p>}
          </motion.div>
        </AnimatePresence>
      </div>
    </>
  );
}

function Value({ node }: { node: CalcNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <span className="num font-display text-4xl font-semibold">{node.display ?? "—"}</span>
      <span className="text-sm text-muted">{node.unit !== "-" ? node.unit : ""}</span>
    </div>
  );
}

function NodeView({ node, push }: { node: CalcNode; push: (id: string) => void }) {
  const { t } = useTranslation();
  const src = node.source;
  return (
    <div className="space-y-5">
      <div>
        <div className="eyebrow mb-1 flex items-center gap-2">
          {src?.kind === "evidence" ? <FileImage className="h-3.5 w-3.5" /> : src?.kind === "refdata" ? <BookMarked className="h-3.5 w-3.5" /> : src?.kind === "assumption" ? <FlaskConical className="h-3.5 w-3.5" /> : src?.kind === "scenario" ? <Sparkles className="h-3.5 w-3.5" /> : <Sigma className="h-3.5 w-3.5" />}
          {src?.kind === "evidence" ? t("lens.source") : src?.kind === "refdata" ? t("lens.refdata") : src?.kind === "assumption" ? t("lens.assumption") : src?.kind === "scenario" ? t("lens.scenario") : t("lens.calc")}
        </div>
        <h2 className="text-base font-semibold leading-snug">{node.label}</h2>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Value node={node} />
        <StatusBadge status={node.status} />
      </div>
      {node.note && <p className="rounded-lg border border-line bg-sunk px-3 py-2 text-xs text-ink2">{node.note}</p>}
      {src?.kind === "evidence" && <EvidenceView node={node} />}
      {(src?.kind === "refdata" || src?.kind === "assumption") && <RefView node={node} />}
      {node.formula && (
        <section>
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
            <div className="eyebrow">{t("lens.formula")}</div>
            {document.documentElement.dataset.ask === "1" && <button
              type="button"
              className="btn-quiet min-h-[32px] px-2 text-[12px] text-accent"
              onClick={() => window.dispatchEvent(new CustomEvent("pramaan:ask", { detail: { node: node.id, q: t("ask.explain_q", { label: node.label, value: `${node.display ?? ""} ${node.unit ?? ""}`.trim() }) } }))}
            >
              <Sparkles className="h-3.5 w-3.5" aria-hidden /> {t("lens.explain")}
            </button>}
          </div>
          <code className="block rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[13px] text-ink">{node.formula}</code>
        </section>
      )}
      {node.children.length > 0 && <Inputs node={node} push={push} />}
      {node.children.length > 0 && <Leaves node={node} push={push} />}
    </div>
  );
}

/** Every source behind a derived number: photos of the exact regions, official values, assumptions. */
function Leaves({ node, push }: { node: CalcNode; push: (id: string) => void }) {
  const { t } = useTranslation();
  const { pid, result, docs } = useProject();
  const [all, setAll] = useState(false);
  const tree = result!.calc_tree;
  const leaves = useMemo(() => {
    const out: CalcNode[] = [];
    const seen = new Set<string>();
    const walk = (id: string) => {
      if (seen.has(id)) return;
      seen.add(id);
      const n = tree[id];
      if (!n) return;
      if (!n.children.length) out.push(n);
      n.children.forEach(walk);
    };
    walk(node.id);
    return out;
  }, [node.id, tree]);
  const ev = leaves.filter((l) => l.source?.kind === "evidence");
  const refs = leaves.filter((l) => l.source?.kind === "refdata");
  const asm = leaves.filter((l) => l.source?.kind === "assumption");
  const docCount = new Set(ev.map((l) => l.source?.doc_id)).size;
  if (!leaves.length) return null;
  const shown = all ? ev : ev.slice(0, 8);
  return (
    <section>
      <div className="eyebrow mb-1.5">{t("lens.sources_title", { defaultValue: "Everything behind this number" })}</div>
      <p className="mb-2 text-[12px] text-ink2">
        {ev.length} {t("lens.values_from", { defaultValue: "values read from" })} {docCount} {t("lens.documents", { defaultValue: "documents" })} · {refs.length} {t("lens.official_values", { defaultValue: "official values" })} · {asm.length} {t("lens.assumptions", { defaultValue: "stated assumptions" })}
      </p>
      {ev.length > 0 && (
        <motion.ul className="grid grid-cols-2 gap-2" variants={stagger(0.04, 0.1)} initial="hidden" animate="show">
          {shown.map((l) => {
            const d = l.source?.doc_id ? docs[l.source.doc_id] : undefined;
            const aspect = d?.width && d?.height ? d.width / d.height : 0.75;
            const box = l.source?.box_2d;
            return (
              <motion.li key={l.id} variants={rise}>
                <button onClick={() => push(l.id)} className="group w-full overflow-hidden rounded-xl border border-line bg-surface text-left transition duration-200 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-hover">
                  {box ? <CropView src={imageUrl(pid, l.source!.doc_id!)} box={[Math.max(0, box[0] - 8), Math.max(0, box[1] - 30), Math.min(1000, box[2] + 8), Math.min(1000, box[3] + 30)]} alt={l.label} imgAspect={aspect} /> : null}
                  <div className="px-2 py-1.5">
                    <div className="flex items-center justify-between gap-1">
                      <span className="num text-[13px] font-semibold">{l.display}</span>
                      <span className={`h-1.5 w-1.5 rounded-full ${{ good: "bg-good", warn: "bg-warn", bad: "bg-bad", neutral: "bg-line2", info: "bg-accent" }[toneOf(l.status)]}`} />
                    </div>
                    <div className="truncate text-[11px] text-muted">{l.label}</div>
                  </div>
                </button>
              </motion.li>
            );
          })}
        </motion.ul>
      )}
      {ev.length > 8 && (
        <button className="btn-quiet mt-1 w-full" onClick={() => setAll((a) => !a)}>
          {all ? "−" : `+${ev.length - 8}`}
        </button>
      )}
      {(refs.length > 0 || asm.length > 0) && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {[...refs, ...asm].map((l) => (
            <li key={l.id}>
              <button onClick={() => push(l.id)} className={`chip hover:border-accent/40 ${l.source?.kind === "assumption" ? "border-accent/30 text-accent" : ""}`}>
                {l.source?.kind === "assumption" ? <FlaskConical className="h-3 w-3" /> : <BookMarked className="h-3 w-3" />} {l.label}: <b className="num">{l.display}</b>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Inputs({ node, push }: { node: CalcNode; push: (id: string) => void }) {
  const { t } = useTranslation();
  const { result } = useProject();
  const tree = result!.calc_tree;
  return (
    <section>
      <div className="eyebrow mb-1.5">{t("lens.inputs")}</div>
      <motion.ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface" variants={stagger(0.05, 0.05)} initial="hidden" animate="show">
        {node.children.map((cid) => {
          const c = tree[cid];
          if (!c) return null;
          return (
            <motion.li key={cid} variants={rise}>
              <button onClick={() => push(cid)} className="group flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-sunk focus-visible:bg-sunk focus-visible:outline-none">
                <span className={`h-8 w-1 shrink-0 rounded-full ${{ good: "bg-good", warn: "bg-warn", bad: "bg-bad", neutral: "bg-line2", info: "bg-accent" }[toneOf(c.status)]}`} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm">{c.label}</span>
                  <span className="block truncate text-[11px] text-muted">{c.source?.kind === "evidence" ? c.source.doc_title : c.source?.locator ?? c.formula ?? ""}</span>
                </span>
                <span className="num shrink-0 text-sm font-semibold">{c.display ?? "—"}</span>
                <span className="w-14 shrink-0 truncate text-[11px] text-muted">{c.unit !== "-" ? c.unit : ""}</span>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
              </button>
            </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}

function EvidenceView({ node }: { node: CalcNode }) {
  const { t } = useTranslation();
  const { pid, docs, evById } = useProject();
  const s = node.source!;
  const doc = s.doc_id ? docs[s.doc_id] : undefined;
  const ev = s.evidence_id ? evById[s.evidence_id] : undefined;
  const src = s.doc_id ? imageUrl(pid, s.doc_id) : "";
  const aspect = doc?.width && doc?.height ? doc.width / doc.height : 0.75;
  const tone = { good: "good", warn: "warn", bad: "bad", neutral: "accent", info: "accent" }[toneOf(node.status)] as "good" | "warn" | "bad" | "accent";
  // read in order: reader 1 (the page), reader 2 (only the crop), then whether they agree
  const second = useAfter(500, [node.id]);
  const verdict = useAfter(950, [node.id]);
  if (doc?.content_type.startsWith("audio/")) {
    return (
      <div className="space-y-3">
        <div className="rounded-xl border border-line bg-surface p-3">
          <div className="eyebrow mb-2">{t("doctype.voice_note", { defaultValue: "Voice note" })}</div>
          <audio controls src={src} className="w-full" />
          <p className="mt-2 whitespace-pre-wrap text-[13px] text-ink2">{ev?.notes}</p>
          <p className="mt-1 font-mono text-[11px] text-muted">{ev?.extractor_model}</p>
        </div>
        {ev?.approved_by && (
          <p className="flex items-center gap-2 rounded-lg border border-warn/40 bg-warnbg px-3 py-2 text-xs text-warnink">
            <UserCheck className="h-4 w-4" /> {t("lens.approved")} {t("lens.by")} <b>{ev.approved_by}</b> · {when(ev.approved_at)}
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <DocImage src={src} box={s.box_2d} alt={`${s.doc_title}: ${node.label}`} aspect={aspect} tone={tone} label={doc ? t(`doctype.${doc.doc_type}`, { defaultValue: doc.doc_type ?? "" }) : undefined} />
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl border border-line bg-surface p-3">
          <div className="eyebrow mb-1">{t("lens.as_read")}</div>
          <div className="font-mono text-lg">{s.value_text}</div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3">
          <div className="eyebrow mb-1">{t("gaps.doc")}</div>
          <div className="truncate text-sm font-medium">{doc?.title || s.doc_title}</div>
          <div className="text-[11px] text-muted">{s.period ?? ""} · box [{s.box_2d?.join(", ")}]</div>
        </div>
      </div>
      {ev && (
        <section>
          <div className="eyebrow mb-1.5">{t("lens.readers")}</div>
          <div className="relative grid gap-3 sm:grid-cols-2 sm:gap-x-9">
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lens.reader1")}</div>
              <div className="font-mono text-lg">{ev.value_text}</div>
              <div className="mt-1 truncate text-[11px] text-muted">{ev.extractor_model}</div>
            </div>
            <motion.div
              className={`rounded-xl border p-3 transition-colors duration-500 ${verdict ? (ev.second_reading?.agrees ? "border-good/40 bg-goodbg" : "border-warn/50 bg-warnbg") : "border-line bg-surface"}`}
              initial={false}
              animate={second ? { opacity: 1, x: 0 } : { opacity: 0, x: -10 }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              <div className="text-[11px] text-ink2">{t("lens.reader2")}</div>
              <div className="font-mono text-lg">{ev.second_reading?.reading_value ?? "—"}</div>
              {ev.second_reading?.corrected_from && <div className="text-[12px] font-medium text-warnink">{t("gaps.crossed_out", { value: ev.second_reading.corrected_from })}</div>}
              <div className="mt-1 truncate text-[11px] text-ink2">{ev.second_reading?.model} · {ev.second_reading?.agrees ? t("lens.agree") : t("lens.disagree")}</div>
            </motion.div>
            <AnimatePresence>
              {verdict && ev.second_reading && (
                <motion.span
                  key="v"
                  className={`absolute left-1/2 top-1/2 hidden h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border bg-surface shadow-card sm:grid ${ev.second_reading.agrees ? "border-good/50 text-goodink" : "border-warn/60 text-warnink"}`}
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 520, damping: 20 }}
                  aria-hidden
                >
                  {ev.second_reading.agrees ? <Check className="h-4 w-4" /> : <span className="font-mono text-[15px] font-semibold">≠</span>}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          {ev.second_reading?.crop_box && (
            <div className="mt-3">
              <CropView src={src} box={ev.second_reading.crop_box} alt="crop" imgAspect={aspect} />
              <p className="mt-1 text-[11px] text-muted">{t("gaps.reader2")}</p>
            </div>
          )}
          {ev.approved_by && (
            <p className="mt-3 flex items-center gap-2 rounded-lg border border-warn/40 bg-warnbg px-3 py-2 text-xs text-warnink">
              <UserCheck className="h-4 w-4" /> {t("lens.approved")} {t("lens.by")} <b>{ev.approved_by}</b> · {when(ev.approved_at)}
            </p>
          )}
        </section>
      )}
      <a className="link inline-flex items-center gap-1 text-sm" href={src} target="_blank" rel="noreferrer">
        {t("lens.open_doc")} <ExternalLink className="h-3.5 w-3.5" />
      </a>
    </div>
  );
}

function RefView({ node }: { node: CalcNode }) {
  const { t } = useTranslation();
  const s = node.source!;
  const cit = s.citation as Record<string, string | number> | undefined;
  return (
    <section className={`space-y-2 rounded-xl border p-3 text-sm ${s.kind === "assumption" ? "border-accent/25 bg-accent/5" : "border-line bg-surface"}`}>
      <div>
        <span className="text-[11px] text-muted">{t("lens.locator")}: </span>
        <span>{s.locator}</span>
      </div>
      {cit && (cit.page || cit.table || cit.article) ? (
        <div className="text-[13px] text-ink2">{[cit.table, cit.article, cit.section && `s.${cit.section}`, cit.page && `p. ${cit.page}`].filter(Boolean).join(" · ")}</div>
      ) : null}
      {s.document && (
        <div className="border-t border-line pt-2">
          <div className="font-medium">{s.document.title}</div>
          <div className="text-[11px] text-muted">
            {t("lens.published")} {s.document.published} · {t("lens.sha", { defaultValue: "SHA-256" })} {s.document.sha256}…
          </div>
          <a className="link mt-1 inline-flex items-center gap-1 text-[13px]" href={s.document.url} target="_blank" rel="noreferrer">
            {t("lens.official")} <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      )}
    </section>
  );
}

/** A number that opens the Evidence Lens. */
export function LensNum({ node, children, className = "" }: { node?: string | null; children: ReactNode; className?: string }) {
  const { open } = useLens();
  if (!node) return <span className={className}>{children}</span>;
  return (
    <button type="button" className={`clickable-num ${className}`} onClick={() => open(node)} title="Open Evidence Lens">
      {children}
    </button>
  );
}

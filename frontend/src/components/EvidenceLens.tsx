import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowLeft, BookMarked, ChevronRight, ExternalLink, FileImage, FlaskConical, ScanSearch, Sigma, Sparkles, UserCheck, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { imageUrl, type CalcNode } from "@/lib/api";
import { useProject } from "@/lib/project";
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
  const open = useCallback((id: string) => setStack([id]), []);
  const value = useMemo(() => ({ open }), [open]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <Dialog.Root open={stack.length > 0} onOpenChange={(o) => !o && setStack([])}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px] data-[state=open]:animate-[rise_.2s_ease-out]" />
          <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] animate-sheet flex-col border-l border-line bg-page shadow-lift focus:outline-none" aria-describedby={undefined}>
            {stack.length > 0 && <LensBody nodeId={stack[stack.length - 1]} depth={stack.length} push={(id) => setStack((s) => [...s, id])} pop={() => setStack((s) => s.slice(0, -1))} />}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </Ctx.Provider>
  );
}

function LensBody({ nodeId, depth, push, pop }: { nodeId: string; depth: number; push: (id: string) => void; pop: () => void }) {
  const { t } = useTranslation();
  const { result } = useProject();
  const node = result?.calc_tree[nodeId];
  return (
    <>
      <header className="flex items-center gap-2 border-b border-line bg-surface px-4 py-3">
        {depth > 1 ? (
          <button className="btn-quiet -ml-2" onClick={pop} aria-label={t("lens.back")}>
            <ArrowLeft className="h-4 w-4" />
          </button>
        ) : (
          <ScanSearch className="h-5 w-5 text-accent" aria-hidden />
        )}
        <Dialog.Title className="flex-1 text-sm font-semibold">
          {t("lens.title")}
          {depth > 1 && <span className="ml-2 text-xs font-normal text-muted">· {depth - 1} ↓</span>}
        </Dialog.Title>
        <Dialog.Close className="btn-quiet -mr-2" aria-label={t("common.close")}>
          <X className="h-4 w-4" />
        </Dialog.Close>
      </header>
      <div className="flex-1 overflow-y-auto p-4 sm:p-5">{node ? <NodeView node={node} push={push} /> : <p className="text-sm text-muted">—</p>}</div>
    </>
  );
}

function Value({ node }: { node: CalcNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <span className="text-4xl font-semibold tracking-tight">{node.display ?? "—"}</span>
      <span className="text-sm text-muted">{node.unit !== "-" ? node.unit : ""}</span>
    </div>
  );
}

function NodeView({ node, push }: { node: CalcNode; push: (id: string) => void }) {
  const { t } = useTranslation();
  const src = node.source;
  return (
    <div className="space-y-5 animate-rise" key={node.id}>
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
          <div className="eyebrow mb-1.5">{t("lens.formula")}</div>
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
        <ul className="grid grid-cols-2 gap-2">
          {shown.map((l) => {
            const d = l.source?.doc_id ? docs[l.source.doc_id] : undefined;
            const aspect = d?.width && d?.height ? d.width / d.height : 0.75;
            const box = l.source?.box_2d;
            return (
              <li key={l.id}>
                <button onClick={() => push(l.id)} className="group w-full overflow-hidden rounded-xl border border-line bg-surface text-left transition hover:border-accent/40">
                  {box ? <CropView src={imageUrl(pid, l.source!.doc_id!)} box={[Math.max(0, box[0] - 8), Math.max(0, box[1] - 30), Math.min(1000, box[2] + 8), Math.min(1000, box[3] + 30)]} alt={l.label} imgAspect={aspect} /> : null}
                  <div className="px-2 py-1.5">
                    <div className="flex items-center justify-between gap-1">
                      <span className="num text-[13px] font-semibold">{l.display}</span>
                      <span className={`h-1.5 w-1.5 rounded-full ${{ good: "bg-good", warn: "bg-warn", bad: "bg-bad", neutral: "bg-line2", info: "bg-accent" }[toneOf(l.status)]}`} />
                    </div>
                    <div className="truncate text-[11px] text-muted">{l.label}</div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
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
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {node.children.map((cid) => {
          const c = tree[cid];
          if (!c) return null;
          return (
            <li key={cid}>
              <button onClick={() => push(cid)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-sunk focus-visible:bg-sunk focus-visible:outline-none">
                <span className={`h-8 w-1 shrink-0 rounded-full ${{ good: "bg-good", warn: "bg-warn", bad: "bg-bad", neutral: "bg-line2", info: "bg-accent" }[toneOf(c.status)]}`} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm">{c.label}</span>
                  <span className="block truncate text-[11px] text-muted">{c.source?.kind === "evidence" ? c.source.doc_title : c.source?.locator ?? c.formula ?? ""}</span>
                </span>
                <span className="num shrink-0 text-sm font-semibold">{c.display ?? "—"}</span>
                <span className="w-14 shrink-0 truncate text-[11px] text-muted">{c.unit !== "-" ? c.unit : ""}</span>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted" aria-hidden />
              </button>
            </li>
          );
        })}
      </ul>
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
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("lens.reader1")}</div>
              <div className="font-mono text-lg">{ev.value_text}</div>
              <div className="mt-1 truncate text-[11px] text-muted">{ev.extractor_model}</div>
            </div>
            <div className={`rounded-xl border p-3 ${ev.second_reading?.agrees ? "border-good/40 bg-goodbg" : "border-warn/50 bg-warnbg"}`}>
              <div className="text-[11px] text-ink2">{t("lens.reader2")}</div>
              <div className="font-mono text-lg">{ev.second_reading?.reading_value ?? "—"}</div>
              <div className="mt-1 truncate text-[11px] text-ink2">{ev.second_reading?.model} · {ev.second_reading?.agrees ? t("lens.agree") : t("lens.disagree")}</div>
            </div>
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

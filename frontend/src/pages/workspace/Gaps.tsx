import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, Check, ChevronDown, Loader2, Pencil, Scale, ScanSearch, UserRound } from "lucide-react";
import { api, imageUrl, type Gap } from "@/lib/api";
import { useProject } from "@/lib/project";
import { DocImage, CropView } from "@/components/DocImage";
import { VoiceAnswer } from "@/components/VoiceAnswer";
import { StatusBadge } from "@/components/Status";
import { useLens } from "@/components/EvidenceLens";

const GROUPS = ["review", "precursor", "activity", "energy", "exports", "extra", "control"];

function gapText(t: (k: string, o?: Record<string, unknown>) => string, g: Gap) {
  const params: Record<string, unknown> = { ...g.params };
  if (Array.isArray(params.missing)) params.missing = (params.missing as string[]).join(", ");
  if (Array.isArray(params.quarters)) params.quarters = (params.quarters as string[]).join(", ");
  const base = `gaps.kinds.${g.kind}`;
  const title = t(`${base}.t`, params);
  let q: string;
  if (g.kind === "precursor_see" || g.kind === "precursor_sefa") q = t(`${base}.${g.params.data === "ACTUAL_VERIFIED" || g.status === "green" ? "q_actual" : "q_default"}`, params);
  else q = t(`${base}.q`, params);
  return { title, q };
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
        <div className="flex-1">
          <h2 className="text-2xl font-semibold tracking-tight">{t("gaps.title")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink2">{t("gaps.lead")}</p>
        </div>
        <div className="flex gap-2">
          {(["red", "amber", "green"] as const).map((k) => (
            <StatusBadge key={k} status={k} label={`${counts[k] ?? 0} · ${t(`status.${k}`)}`} />
          ))}
        </div>
      </div>

      <section>
        <h3 className="eyebrow mb-2">{t("gaps.group_review")}</h3>
        {reviews.length ? (
          <div className="space-y-4">
            {reviews.map((g) => (
              <ReviewCard key={g.id} g={g} />
            ))}
          </div>
        ) : (
          <p className="flex items-center gap-2 rounded-xl border border-good/30 bg-goodbg px-4 py-3 text-sm text-goodink">
            <Check className="h-4 w-4" /> {t("gaps.all_clear")}
          </p>
        )}
      </section>

      {GROUPS.filter((gr) => gr !== "review").map((gr) => (
        <GapGroup key={gr} group={gr} items={gaps.filter((g) => g.group === gr)} />
      ))}
      <div className="flex justify-end">
        <Link to={`/p/${pid}/report`} className="btn-primary">
          {t("steps.report")} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function GapGroup({ group, items }: { group: string; items: Gap[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  const attention = items.filter((g) => g.status === "red" || g.status === "amber");
  const rest = items.filter((g) => g.status !== "red" && g.status !== "amber");
  const shown = open || attention.length === 0 ? [...attention, ...rest] : attention;
  return (
    <section>
      <h3 className="eyebrow mb-2">{t(`gaps.group_${group}`)}</h3>
      <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {shown.map((g) => (
          <GapRow key={g.id} g={g} />
        ))}
        {attention.length > 0 && rest.length > 0 && (
          <li>
            <button className="flex min-h-[44px] w-full items-center gap-2 px-4 text-[13px] text-ink2 hover:bg-sunk" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
              <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
              {open ? t("gaps.hide_ok", { defaultValue: "Hide items that are OK" }) : t("gaps.show_ok", { defaultValue: "Show {{n}} items that are OK", n: rest.length })}
            </button>
          </li>
        )}
      </ul>
    </section>
  );
}

function GapRow({ g }: { g: Gap }) {
  const { t } = useTranslation();
  const { open } = useLens();
  const { title, q } = gapText(t, g);
  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
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
  const { t } = useTranslation();
  const { pid, evById, docs, refresh } = useProject();
  const ev = evById[g.evidence_ids[0]];
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(ev?.value_text ?? "");
  if (!ev) return null;
  const doc = docs[ev.doc_id];
  const aspect = doc?.width && doc?.height ? doc.width / doc.height : 0.75;
  const { title, q } = gapText(t, g);
  async function act(action: "approve" | "edit", value?: string) {
    setBusy(value ?? action);
    try {
      await api.patchEvidence(pid, ev.id, action === "edit" ? { action, value_text: value!, value_num: value!.replace(/[^\d.]/g, ""), user: "Owner (demo)" } : { action, user: "Owner (demo)" });
      await refresh();
    } finally {
      setBusy(null);
      setEditing(false);
    }
  }
  return (
    <div className="card overflow-hidden border-warn/50">
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
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-line bg-surface p-3">
              <div className="text-[11px] text-muted">{t("gaps.reader1")}</div>
              <div className="font-mono text-2xl">{ev.value_text}</div>
              <div className="truncate text-[11px] text-muted">{ev.extractor_model}</div>
            </div>
            <div className="rounded-xl border border-warn/50 bg-warnbg p-3">
              <div className="text-[11px] text-ink2">{t("gaps.reader2")}</div>
              <div className="font-mono text-2xl">{ev.second_reading?.reading_value ?? "—"}</div>
              <div className="truncate text-[11px] text-ink2">{ev.second_reading?.model}</div>
            </div>
          </div>
          {g.params.balance && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-line bg-sunk px-3 py-2 text-[13px]">
              <Scale className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
              <span>
                <b>{t("gaps.balance_t", { defaultValue: "Mass-balance check" })}</b> ({ev.period}): {g.params.balance.formula} = <b className="num">{g.params.balance.implied} t</b>
                {g.params.balance.supports && (
                  <span className="text-goodink"> → {t(g.params.balance.supports === "first" ? "gaps.supports_1" : "gaps.supports_2", { defaultValue: g.params.balance.supports === "first" ? "supports reader 1" : "supports reader 2" })}</span>
                )}
              </span>
            </div>
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
                <input value={val} onChange={(e) => setVal(e.target.value)} inputMode="decimal" className="min-h-[44px] flex-1 rounded-xl border border-line2 bg-surface px-3 font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" aria-label={t("gaps.edit")} />
                <button className="btn-primary" disabled={!!busy}>{t("gaps.save")}</button>
                <button type="button" className="btn-quiet" onClick={() => setEditing(false)}>{t("gaps.cancel")}</button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function NoResult() {
  const { t } = useTranslation();
  const { pid } = useProject();
  return (
    <div className="card mx-auto max-w-lg p-8 text-center">
      <p className="text-sm text-ink2">{t("timeline.empty")}</p>
      <Link to={`/p/${pid}/capture`} className="btn-primary mt-4">
        {t("capture.run")}
      </Link>
    </div>
  );
}

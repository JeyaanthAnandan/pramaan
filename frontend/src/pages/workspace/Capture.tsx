import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { ArrowRight, Camera, Check, FolderUp, Loader2, Mic, Play, RotateCw, Smartphone, Upload } from "lucide-react";
import { api, imageUrl, type Doc } from "@/lib/api";
import { useProject } from "@/lib/project";
import { rise, stagger } from "@/lib/motion";
import { AgentTimeline, useRunEvents } from "@/components/AgentTimeline";
import { SetupCard } from "@/components/Setup";
import { useToast } from "@/components/Toast";
import { QrCode } from "@/components/QrCode";
import { passcodeFor } from "@/lib/session";

export default function Capture() {
  const { t, i18n } = useTranslation();
  const { pid, bundle, evidence, refresh } = useProject();
  const [params, setParams] = useSearchParams();
  const [runId, setRunId] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const toast = useToast();

  const lastRunId = bundle?.last_run?.id ?? null;
  const activeId = runId ?? (bundle?.running ? lastRunId : null);
  const { events, ended } = useRunEvents(pid, activeId, async () => {
    await refresh();
  });
  const past = useQuery({ queryKey: ["run", pid, lastRunId], queryFn: () => api.run(pid, lastRunId!), enabled: !!lastRunId && !activeId });
  const shownEvents = activeId ? events : past.data?.events ?? [];
  // the stream may have missed the end (a dropped connection): the project's own state settles it
  const settled = !!activeId && bundle?.last_run?.id === activeId && bundle.last_run.status !== "running";
  const shownEnded = activeId ? (ended ?? (settled ? bundle!.last_run!.status : null)) : past.data?.status ?? null;
  const running = !!activeId && !ended && !settled;

  async function start() {
    setErr(null);
    try {
      const r = await api.startRun(pid, i18n.language);
      setMode(r.mode);
      setRunId(r.run_id);
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  useEffect(() => {
    if (params.get("autorun") === "1" && bundle && !bundle.running && !runId) {
      params.delete("autorun");
      setParams(params, { replace: true });
      void start();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle]);

  async function upload(files: FileList | File[] | null) {
    if (!files || !files.length) return;
    setUploading(true);
    setErr(null);
    try {
      await api.upload(pid, Array.from(files));
      await refresh();
      toast(t("capture.upload_ok", { n: files.length }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  const docs = bundle?.documents ?? [];
  const evCount: Record<string, number> = {};
  evidence?.forEach((e) => (evCount[e.doc_id] = (evCount[e.doc_id] ?? 0) + 1));
  const geminiOff = health.data && !health.data.models?.gemini_configured;
  const compactDrop = docs.length > 0; // documents are in: the drop zone steps back

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-6">
        <SetupCard />
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            void upload(e.dataTransfer.files);
          }}
          className={`card flex border-2 border-dashed transition duration-200 ${compactDrop ? "flex-col items-start gap-3 px-4 py-4 sm:flex-row sm:items-center" : "flex-col items-center justify-center gap-3 px-6 py-8 text-center"} ${drag ? "scale-[1.01] border-accent bg-accent/5" : "border-line2"}`}
        >
          <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl transition-colors ${drag ? "bg-accent/15" : "bg-sunk"}`}>
            {uploading ? <Loader2 className="h-6 w-6 animate-spin text-accent" /> : <Upload className={`h-6 w-6 transition-transform duration-300 ${drag ? "-translate-y-1 text-accent" : "text-ink2"}`} />}
          </span>
          <div className={compactDrop ? "min-w-0 flex-1" : ""}>
            <div className="text-base font-semibold">{t("capture.drop")}</div>
            <p className="text-[12px] text-muted">{t("capture.formats")}</p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button className={compactDrop ? "btn-ghost" : "btn-primary"} onClick={() => camRef.current?.click()}>
              <Camera className="h-4 w-4" /> {t("capture.camera")}
            </button>
            <span className="text-sm text-muted">{t("capture.or")}</span>
            <button className="btn-ghost" onClick={() => fileRef.current?.click()}>
              <FolderUp className="h-4 w-4" /> {t("capture.choose")}
            </button>
          </div>
          <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => upload(e.target.files)} />
          <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
        </div>

        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold">
              {t("capture.docs")} <span className="num text-muted">({docs.length})</span>
            </h2>
            <div className="ml-auto flex items-center gap-2">
              <button className={`btn-primary ${!lastRunId && docs.length ? "glint" : ""}`} onClick={start} disabled={running || !docs.length}>
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : lastRunId ? <RotateCw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {running ? t("capture.running") : lastRunId ? t("capture.rerun") : t("capture.run")}
              </button>
              {bundle?.has_result && !running && (
                <Link to={`/p/${pid}/gaps`} className="btn-ghost nudge">
                  {t("capture.next")} <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </div>
          </div>
          {geminiOff && (
            <p className="mb-3 rounded-xl border border-accent/25 bg-accent/5 px-3 py-2 text-[13px] text-ink2">
              {bundle?.project.is_demo ? t("capture.mode_replay") : t("capture.own_needs_live", { defaultValue: "Reading your own documents needs live Gemini, which is not configured on this server. The sample factory works without it." })}
            </p>
          )}
          {err && <p className="mb-3 rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink">{err}</p>}
          {!docs.length ? (
            <p className="rounded-xl border border-line bg-surface px-4 py-8 text-center text-sm text-muted">{t("capture.none")}</p>
          ) : (
            <motion.ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4" variants={stagger(0.025, 0.05)} initial="hidden" animate="show">
              {docs.map((d) => (
                <DocCard key={d.id} d={d} pid={pid} count={evCount[d.id] ?? 0} busy={running && d.state !== "extracted"} />
              ))}
            </motion.ul>
          )}
        </div>
      </div>
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">{activeId ? t("timeline.title") : t("timeline.receipt")}</h2>
            {(mode || past.data?.mode) && <span className="chip font-mono">{mode ?? past.data?.mode}</span>}
          </div>
          <AgentTimeline events={shownEvents} ended={shownEnded} mode={mode ?? past.data?.mode} />
        </div>
        <PhoneHandoff pid={pid} />
      </aside>
    </div>
  );
}

function DocCard({ d, pid, count, busy }: { d: Doc; pid: string; count: number; busy: boolean }) {
  const { t } = useTranslation();
  return (
    <motion.li variants={rise} className="card card-hover group overflow-hidden">
      <div className="relative aspect-[4/5] overflow-hidden bg-sunk">
        {d.content_type.startsWith("audio/") ? (
          <div className="grid h-full w-full place-items-center bg-sunk text-muted">
            <Mic className="h-8 w-8" aria-hidden />
          </div>
        ) : (
          <img src={imageUrl(pid, d.id)} alt={d.title || d.filename} loading="lazy" className="h-full w-full object-cover object-top transition duration-500 group-hover:scale-[1.04]" />
        )}
        {busy && (
          // being read: a scanner line runs down the page
          <div className="absolute inset-0 overflow-hidden bg-page/25">
            <div className="absolute inset-x-0 top-0 h-1/3 animate-scany bg-gradient-to-b from-transparent via-accent/25 to-accent/60" />
            <div className="absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-md bg-surface/90 px-1.5 py-0.5 text-[10px] font-semibold text-accent shadow-card">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> {t("capture.reading")}
            </div>
          </div>
        )}
        {d.languages?.length > 0 && (
          <div className="absolute right-1.5 top-1.5 flex gap-1">
            {d.languages.map((l) => (
              <span key={l} className="rounded bg-surface/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ink2 shadow-card">{l}</span>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-1 p-2.5">
        <div className="truncate text-[13px] font-medium" title={d.title || d.filename}>{d.doc_type ? t(`doctype.${d.doc_type}`, { defaultValue: d.doc_type }) : d.filename}</div>
        <div className="flex items-center justify-between text-[11px] text-muted">
          <span className="truncate">{d.period?.[0] ? d.period[0].slice(0, 7) : d.state === "uploaded" ? t("capture.uploaded") : ""}</span>
          {count > 0 && (
            <span key={count} className="num inline-flex animate-pop items-center gap-0.5 text-goodink">
              <Check className="h-3 w-3" aria-hidden />
              {count} {t("capture.extracted")}
            </span>
          )}
        </div>
      </div>
    </motion.li>
  );
}

/** Bills and registers live on the shop floor: scan to keep adding photos from a phone. For a private
 *  project the passcode rides in the link's #fragment, which browsers never send to the server; the
 *  phone unlocks the project with it and drops it from the address bar. */
function PhoneHandoff({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const code = passcodeFor(pid);
  const url = `${window.location.origin}/p/${pid}/capture${code ? `#k=${code.replace(/[^A-Za-z0-9-]/g, "")}` : ""}`;
  return (
    <div className="card mt-4 hidden items-center gap-4 p-4 lg:flex">
      <QrCode value={url} label={t("capture.handoff_t")} size={112} />
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-sm font-semibold">
          <Smartphone className="h-4 w-4 text-accent" aria-hidden /> {t("capture.handoff_t")}
        </div>
        <p className="mt-1 text-[12px] text-muted">{t(code ? "capture.handoff_private" : "capture.handoff_d")}</p>
      </div>
    </div>
  );
}

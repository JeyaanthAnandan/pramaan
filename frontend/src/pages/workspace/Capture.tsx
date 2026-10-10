import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Camera, FolderUp, Loader2, Mic, Play, RotateCw, Upload } from "lucide-react";
import { api, imageUrl, type Doc } from "@/lib/api";
import { useProject } from "@/lib/project";
import { AgentTimeline, useRunEvents } from "@/components/AgentTimeline";

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

  const lastRunId = bundle?.last_run?.id ?? null;
  const activeId = runId ?? (bundle?.running ? lastRunId : null);
  const { events, ended } = useRunEvents(pid, activeId, async () => {
    await refresh();
  });
  const past = useQuery({ queryKey: ["run", pid, lastRunId], queryFn: () => api.run(pid, lastRunId!), enabled: !!lastRunId && !activeId });
  const shownEvents = activeId ? events : past.data?.events ?? [];
  const shownEnded = activeId ? ended : past.data?.status ?? null;
  const running = !!activeId && !ended;

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

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="space-y-6">
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
          className={`card flex flex-col items-center justify-center gap-3 border-2 border-dashed px-6 py-8 text-center transition ${drag ? "border-accent bg-accent/5" : "border-line2"}`}
        >
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-sunk">{uploading ? <Loader2 className="h-6 w-6 animate-spin text-accent" /> : <Upload className="h-6 w-6 text-ink2" />}</span>
          <div className="text-base font-semibold">{t("capture.drop")}</div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button className="btn-primary" onClick={() => camRef.current?.click()}>
              <Camera className="h-4 w-4" /> {t("capture.camera")}
            </button>
            <span className="text-sm text-muted">{t("capture.or")}</span>
            <button className="btn-ghost" onClick={() => fileRef.current?.click()}>
              <FolderUp className="h-4 w-4" /> {t("capture.choose")}
            </button>
          </div>
          <p className="text-[12px] text-muted">{t("capture.formats")}</p>
          <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => upload(e.target.files)} />
          <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
        </div>

        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold">
              {t("capture.docs")} <span className="num text-muted">({docs.length})</span>
            </h2>
            <div className="ml-auto flex items-center gap-2">
              <button className="btn-primary" onClick={start} disabled={running || !docs.length}>
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : lastRunId ? <RotateCw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {running ? t("capture.running") : lastRunId ? t("capture.rerun") : t("capture.run")}
              </button>
              {bundle?.has_result && !running && (
                <Link to={`/p/${pid}/gaps`} className="btn-ghost">
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
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
              {docs.map((d) => (
                <DocCard key={d.id} d={d} pid={pid} count={evCount[d.id] ?? 0} busy={running && d.state !== "extracted"} />
              ))}
            </ul>
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
      </aside>
    </div>
  );
}

function DocCard({ d, pid, count, busy }: { d: Doc; pid: string; count: number; busy: boolean }) {
  const { t } = useTranslation();
  return (
    <li className="card overflow-hidden">
      <div className="relative aspect-[4/5] overflow-hidden bg-sunk">
        {d.content_type.startsWith("audio/") ? (
          <div className="grid h-full w-full place-items-center bg-sunk text-muted">
            <Mic className="h-8 w-8" aria-hidden />
          </div>
        ) : (
          <img src={imageUrl(pid, d.id)} alt={d.title || d.filename} loading="lazy" className="h-full w-full object-cover object-top transition duration-500 hover:scale-[1.03]" />
        )}
        {busy && <div className="absolute inset-0 grid place-items-center bg-page/50 backdrop-blur-[1px]"><Loader2 className="h-5 w-5 animate-spin text-accent" /></div>}
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
          {count > 0 && <span className="num">{count} {t("capture.extracted")}</span>}
        </div>
      </div>
    </li>
  );
}

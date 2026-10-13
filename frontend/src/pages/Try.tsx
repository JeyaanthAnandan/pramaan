import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight, Camera, CheckCircle2, CircleDashed, Factory, ImageUp, Loader2, Lock, RotateCcw, ScanEye, ScanText, Tags, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { lastProject, rememberProject } from "@/lib/session";
import { EASE, Stamp, rise, stagger } from "@/lib/motion";
import { ms } from "@/lib/format";
import { CropView } from "@/components/DocImage";

interface Status { live: boolean; reader1: string; reader2: string; samples: { name: string; title: string }[]; max_checks: number }
interface Field { id: string; field_key: string; label: string; value_text: string; value_num: string | null; unit: string; box_2d: number[] | null; period: string | null }
interface Check { reading: string; agrees: boolean; reason: string; corrected_from: string | null; crop_box?: number[] }
interface Cls { doc_type: string; title: string; languages: string[]; confidence: number; ms: number }
interface Done { ms: number; second_ms?: number; tokens: number; agree: number; review: number; unchecked?: number; note?: string }
interface RunState {
  phase: "classify" | "extract" | "check" | "done" | "error";
  live: boolean; reader1: string; reader2: string; image: string;
  cls?: Cls; extractMs?: number; fields: Field[]; checking: string[]; checks: Record<string, Check>; done?: Done; error?: string;
}

/** Server-sent events from a POST (EventSource only does GET): one JSON object per event. */
async function* sse(res: Response): AsyncGenerator<Record<string, any>> {
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) if (line.startsWith("data: ")) yield JSON.parse(line.slice(6));
    }
  }
}

const SHOWABLE = /^image\/(jpeg|png|webp|gif)$/;

/** Try one photo: the three reading steps of a full run on a single page, live, in front of you.
 *  Boxes appear on the photo as reader 1 returns them and turn green (or amber) as the blind second
 *  reads land. Nothing is stored. Without live Gemini the bundled samples replay their recording. */
export default function Try() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const reduce = useReducedMotion();
  const status = useQuery({ queryKey: ["try"], queryFn: async () => (await fetch("/api/try")).json() as Promise<Status> });
  const [run, setRun] = useState<RunState | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [aspect, setAspect] = useState(0.8);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const live = status.data?.live ?? false;
  useEffect(() => () => abort.current?.abort(), []);
  // when the reading ends, open the first value a person has to check: its crop shows why
  useEffect(() => {
    if (run?.phase !== "done") return;
    const first = run.fields.find((f) => run.checks[f.id] && !run.checks[f.id].agrees);
    if (first) setSel((s) => s ?? first.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.phase]);

  async function start(kind: { sample: string } | { file: File }) {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setSel(null);
    const sample = "sample" in kind ? kind.sample : null;
    const file = "file" in kind ? kind.file : null;
    const image = sample ? `/api/try/sample/${sample}/image` : file && SHOWABLE.test(file.type) ? URL.createObjectURL(file) : "";
    setRun({ phase: "classify", live, reader1: status.data?.reader1 ?? "", reader2: status.data?.reader2 ?? "", image, fields: [], checking: [], checks: {} });
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    let ended = false;
    try {
      let body: FormData | undefined;
      if (file) {
        body = new FormData();
        body.append("file", file);
      }
      const res = await fetch(sample ? `/api/try/sample/${sample}` : "/api/try", { method: "POST", body, signal: ctl.signal });
      if (!res.ok) {
        let msg = res.statusText;
        try {
          msg = (await res.json()).detail ?? msg;
        } catch { /* keep the status text */ }
        setRun((r) => r && { ...r, phase: "error", error: res.status === 429 ? t("try.too_many") : msg });
        return;
      }
      for await (const ev of sse(res)) {
        if (ev.stage === "start") setRun((r) => r && { ...r, live: ev.live, reader1: ev.reader1, reader2: ev.reader2, image: ev.image ?? r.image });
        else if (ev.stage === "classified") setRun((r) => r && { ...r, cls: ev as Cls, phase: "extract" });
        else if (ev.stage === "extracted") setRun((r) => r && { ...r, fields: ev.fields, checking: ev.checking, extractMs: ev.ms, phase: "check" });
        else if (ev.stage === "checked") setRun((r) => r && { ...r, checks: { ...r.checks, [ev.id]: ev as Check } });
        else if (ev.stage === "done") {
          ended = true;
          setRun((r) => r && { ...r, done: ev as Done, phase: "done" });
        } else if (ev.stage === "error") {
          ended = true;
          setRun((r) => r && { ...r, phase: "error", error: ev.message });
        }
      }
      if (!ended) setRun((r) => r && { ...r, phase: "error", error: t("try.dropped") });
    } catch (e) {
      if (!ctl.signal.aborted) setRun((r) => r && { ...r, phase: "error", error: String((e as Error).message) });
    }
  }

  async function wholeFactory() {
    setBusy(true);
    try {
      const r = await api.demoLoad(false);
      rememberProject(r.project_id);
      nav(`/p/${r.project_id}/report`);
    } catch (e) {
      const prev = lastProject();
      if (e instanceof ApiError && e.status === 429 && prev?.startsWith("demo-")) nav(`/p/${prev}/report`);
      else setRun((r) => r && { ...r, error: String((e as Error).message) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 pt-8 sm:px-6">
      <motion.header variants={stagger(0.06)} initial="hidden" animate="show" className="max-w-3xl">
        <motion.div variants={rise} className="eyebrow">{t("try.eyebrow")}</motion.div>
        <motion.h1 variants={rise} className="mt-2 text-[30px] font-semibold leading-tight tracking-tight sm:text-[40px]">{t("try.title")}</motion.h1>
        <motion.p variants={rise} className="mt-3 text-[16px] leading-relaxed text-ink2">{t("try.lead")}</motion.p>
        {status.data && !live && (
          <motion.p variants={rise} className="mt-3 rounded-lg border border-line bg-sunk px-3 py-2 text-[13px] text-ink2">{t("try.replay_note")}</motion.p>
        )}
      </motion.header>

      <AnimatePresence mode="wait">
        {!run ? (
          <motion.section key="pick" className="mt-8" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.25, ease: EASE }}>
            <h2 className="eyebrow">{t("try.pick")}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {(status.data?.samples ?? []).map((s, i) => (
                <motion.button
                  key={s.name}
                  type="button"
                  className="card group overflow-hidden text-left transition hover:-translate-y-0.5 hover:shadow-lift focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                  onClick={() => start({ sample: s.name })}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * i, duration: 0.3, ease: EASE }}
                >
                  <div className="aspect-[4/3] overflow-hidden bg-sunk">
                    <img src={`/api/try/sample/${s.name}/image`} alt="" className="h-full w-full object-cover object-top transition duration-500 group-hover:scale-[1.03]" loading="lazy" />
                  </div>
                  <div className="p-3">
                    <div className="text-[14px] font-semibold">{t(`try.sample_${s.name.split("-")[0]}`, { defaultValue: s.title })}</div>
                    <div className="mt-0.5 text-[12px] text-muted">{t("app.sample")}</div>
                  </div>
                </motion.button>
              ))}
              <motion.div className="card flex flex-col p-4" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 0.3, ease: EASE }}>
                <div className="flex items-center gap-2 text-[14px] font-semibold"><ImageUp className="h-4 w-4 text-accent" aria-hidden /> {t("try.yours")}</div>
                <p className="mt-1 text-[13px] text-ink2">{t("try.yours_d")}</p>
                <div className="mt-auto flex flex-col gap-2 pt-4">
                  <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => e.target.files?.[0] && start({ file: e.target.files[0] })} />
                  <input ref={fileRef} type="file" accept="image/*,application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && start({ file: e.target.files[0] })} />
                  <button className="btn-primary min-h-[44px]" onClick={() => camRef.current?.click()} disabled={!live}>
                    <Camera className="h-4 w-4" /> {t("try.camera")}
                  </button>
                  <button className="btn-ghost min-h-[44px]" onClick={() => fileRef.current?.click()} disabled={!live}>
                    {t("try.choose")}
                  </button>
                  {!live && status.data && <p className="text-[12px] text-muted">{t("try.yours_off")}</p>}
                </div>
              </motion.div>
            </div>
            <p className="mt-4 flex items-center gap-1.5 text-[12px] text-muted"><Lock className="h-3.5 w-3.5" aria-hidden /> {t("try.private")}</p>
          </motion.section>
        ) : (
          <motion.section key="run" className="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <Photo run={run} sel={sel} onSelect={setSel} onAspect={setAspect} />
            <div className="flex flex-col gap-4">
              <Steps run={run} />
              {run.phase === "error" && (
                <p className="flex items-start gap-2 rounded-lg border border-bad/30 bg-badbg px-3 py-2 text-sm text-badink" role="alert">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {run.error || t("try.error")}
                </p>
              )}
              {run.done?.note === "not_cbam" && <p className="rounded-lg border border-line bg-sunk px-3 py-2 text-sm text-ink2">{t("try.not_cbam")}</p>}
              {run.fields.length > 0 && <Values run={run} sel={sel} onSelect={setSel} aspect={aspect} />}
              {(run.phase === "done" || run.phase === "error") && (
                <motion.div className="flex flex-wrap gap-2" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }}>
                  <button className="btn-ghost min-h-[44px]" onClick={() => setRun(null)}>
                    <RotateCcw className="h-4 w-4" /> {t("try.again")}
                  </button>
                  <button className="btn-primary min-h-[44px]" onClick={wholeFactory} disabled={busy}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Factory className="h-4 w-4" />} {t("try.full")} <ArrowRight className="h-4 w-4" />
                  </button>
                </motion.div>
              )}
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}

function tone(f: Field, run: RunState): "pending" | "good" | "warn" | "idle" {
  const c = run.checks[f.id];
  if (c) return c.agrees ? "good" : "warn";
  return run.checking.includes(f.id) && run.phase !== "error" ? "pending" : "idle";
}

const BOX = {
  pending: "border-accent/80 bg-accent/10",
  good: "border-good bg-good/10",
  warn: "border-warn bg-warn/20",
  idle: "border-line2 bg-transparent",
};

/** The page as the readers saw it, with every value's box; a reading beam runs while reader 1 reads. */
function Photo({ run, sel, onSelect, onAspect }: { run: RunState; sel: string | null; onSelect: (id: string) => void; onAspect: (a: number) => void }) {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const [loaded, setLoaded] = useState(false);
  const reading = run.phase === "classify" || run.phase === "extract";
  return (
    <div className="lg:sticky lg:top-24">
      <div className="relative overflow-hidden rounded-xl border border-line bg-sunk">
        {run.image ? (
          <img src={run.image} alt={run.cls?.title || t("try.photo")} className={`block w-full transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`} onLoad={(e) => {
              setLoaded(true);
              const im = e.currentTarget;
              if (im.naturalHeight) onAspect(im.naturalWidth / im.naturalHeight);
            }} draggable={false} />
        ) : (
          <div className="grid aspect-[3/4] place-items-center text-muted"><Loader2 className="h-6 w-6 animate-spin" aria-hidden /></div>
        )}
        {reading && !reduce && (
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
            <div className="absolute inset-x-0 top-0 h-1/3 animate-scany bg-gradient-to-b from-transparent via-accent/25 to-transparent" />
          </div>
        )}
        {loaded &&
          run.fields.map((f, i) => {
            if (!f.box_2d) return null;
            const [y0, x0, y1, x1] = f.box_2d;
            const k = tone(f, run);
            return (
              <motion.button
                key={f.id}
                type="button"
                className={`absolute rounded-[3px] border-2 transition-colors duration-300 ${BOX[k]} ${sel === f.id ? "ring-2 ring-ink ring-offset-1" : ""} ${k === "pending" && !reduce ? "animate-pulse" : ""}`}
                style={{ top: `${(y0 - 4) / 10}%`, left: `${(x0 - 5) / 10}%`, height: `${(y1 - y0 + 8) / 10}%`, width: `${(x1 - x0 + 10) / 10}%` }}
                initial={reduce ? false : { opacity: 0, scale: 1.4 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: reduce ? 0 : Math.min(i * 0.035, 1.2), duration: 0.3, ease: EASE }}
                onClick={() => onSelect(f.id)}
                aria-label={`${f.label}: ${f.value_text}`}
              />
            );
          })}
      </div>
      {run.phase === "done" && run.done && run.done.note !== "not_cbam" && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted">
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm border-2 border-good bg-good/10" aria-hidden /> {t("try.legend_agree")}</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm border-2 border-warn bg-warn/20" aria-hidden /> {t("try.legend_check")}</span>
        </div>
      )}
    </div>
  );
}

/** The three steps of a full run, each with its model, result and time. */
function Steps({ run }: { run: RunState }) {
  const { t } = useTranslation();
  const n = Object.keys(run.checks).length;
  const stepState = (k: number) => {
    const at = { classify: 0, extract: 1, check: 2, done: 3, error: -1 }[run.phase];
    if (run.phase === "error") return k === 0 ? (run.cls ? "done" : "error") : k === 1 ? (run.extractMs !== undefined ? "done" : run.cls ? "error" : "idle") : run.done ? "done" : run.extractMs !== undefined ? "error" : "idle";
    if (run.done?.note === "not_cbam") return k === 0 ? "done" : "skip";
    return k < at ? "done" : k === at ? "run" : "idle";
  };
  const conf = run.cls ? Math.round(run.cls.confidence * 100) : 0;
  const rows = [
    {
      icon: Tags, title: t("try.step_classify"), model: run.reader1,
      detail: run.cls ? `${t(`doctype.${run.cls.doc_type}`, { defaultValue: run.cls.doc_type })}${run.cls.languages.length ? ` · ${run.cls.languages.join("/")}` : ""}${conf ? ` · ${t("try.conf", { p: conf })}` : ""}` : "",
      time: run.cls?.ms,
    },
    { icon: ScanText, title: t("try.step_read"), model: run.reader1, detail: run.extractMs !== undefined ? t("try.values", { n: run.fields.length }) : "", time: run.extractMs },
    {
      icon: ScanEye, title: t("try.step_check"), model: run.reader2,
      detail: run.checking.length ? (run.done ? `${t("try.agree_n", { n: run.done.agree })} · ${t("try.review_n", { n: run.done.review })}` : `${n}/${run.checking.length}`) : "",
      time: run.done?.second_ms,
    },
  ];
  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
        <span className={`chip ${run.live ? "border-accent/30 bg-accent/5 text-accent" : ""}`}>{run.live ? t("try.live_badge") : t("try.replay_badge")}</span>
        {run.cls?.title && <span className="truncate text-[13px] text-ink2">{run.cls.title}</span>}
        {run.done && (
          <span className="ml-auto text-[12px] text-muted">
            {t("try.total", { s: (run.done.ms / 1000).toFixed(1) })}
            {run.done.tokens > 0 && ` · ${t("try.tokens", { n: run.done.tokens.toLocaleString() })}`}
          </span>
        )}
      </div>
      <ol className="divide-y divide-line" aria-live="polite">
        {rows.map((r, k) => {
          const st = stepState(k);
          const Icon = r.icon;
          return (
            <li key={k} className={`flex items-start gap-3 px-4 py-3 transition-opacity ${st === "idle" || st === "skip" ? "opacity-50" : ""}`}>
              <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border ${st === "done" ? "border-good/40 bg-goodbg text-goodink" : st === "run" ? "border-accent/40 bg-accent/10 text-accent" : st === "error" ? "border-bad/40 bg-badbg text-badink" : "border-line bg-sunk text-muted"}`}>
                {st === "run" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : st === "done" ? <CheckCircle2 className="h-4 w-4 animate-pop" aria-hidden /> : <Icon className="h-4 w-4" aria-hidden />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-[14px] font-semibold">{r.title}</span>
                  {r.model && <span className="chip font-mono text-[11px]">{r.model}</span>}
                  {r.time !== undefined && st === "done" && <span className="num ml-auto text-[12px] text-muted">{ms(r.time)}</span>}
                </div>
                <div className="mt-0.5 min-h-[18px] text-[13px] text-ink2">{r.detail || (st === "run" ? t("try.working") : "")}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Every value: what reader 1 read on the page, what reader 2 read in the crop alone, and the verdict. */
function Values({ run, sel, onSelect, aspect }: { run: RunState; sel: string | null; onSelect: (id: string) => void; aspect: number }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (sel) ref.current?.querySelector(`[data-id="${sel}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [sel]);
  const review = run.fields.filter((f) => run.checks[f.id] && !run.checks[f.id].agrees).length;
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="text-[14px] font-semibold">{t("try.values", { n: run.fields.length })}</span>
        {run.phase === "done" && (review ? <Stamp tone="warn" className="ml-auto">{t("try.review_n", { n: review })}</Stamp> : <Stamp className="ml-auto">{t("try.all_agree")}</Stamp>)}
      </div>
      <div className="hidden grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-3 border-b border-line bg-sunk/60 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted sm:grid">
        <span>{t("try.h_value")}</span><span>{t("try.h_r1")}</span><span>{t("try.h_r2")}</span><span className="w-16 text-right">{t("try.h_verdict")}</span>
      </div>
      <div ref={ref} className="divide-y divide-line sm:max-h-[560px] sm:overflow-y-auto">
        {run.fields.map((f, i) => {
          const c = run.checks[f.id];
          const k = tone(f, run);
          return (
            <div key={f.id} data-id={f.id}>
            <motion.button
              type="button"
              onClick={() => onSelect(f.id)}
              className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 px-4 py-2 text-left transition-colors sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto] ${sel === f.id ? "bg-accent/5" : "hover:bg-sunk/60"}`}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: Math.min(i * 0.03, 0.9), duration: 0.25, ease: EASE }}
            >
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-medium">{f.label}</span>
                {f.period && <span className="block text-[11px] text-muted">{f.period}</span>}
              </span>
              <span className="col-start-1 min-w-0 truncate font-mono text-[13px] sm:col-start-auto"><span className="mr-1.5 font-sans text-[10px] uppercase tracking-wide text-muted sm:hidden">{t("try.r1_short")}</span>{f.value_text}{f.unit && <span className="text-muted"> {f.unit}</span>}</span>
              <span className="col-start-1 min-w-0 truncate font-mono text-[13px] text-ink2 sm:col-start-auto"><span className="mr-1.5 font-sans text-[10px] uppercase tracking-wide text-muted sm:hidden">{t("try.r2_short")}</span>
                {c ? (c.reading || "—") : k === "pending" ? <span className="inline-flex items-center gap-1 text-muted"><Loader2 className="h-3 w-3 animate-spin" aria-hidden />{t("try.working")}</span> : "—"}
                {c?.corrected_from ? <span className="block font-sans text-[11px] text-warnink">{t("try.corrected", { v: c.corrected_from })}</span> : c && !c.agrees && c.reason ? <span className="block truncate font-sans text-[11px] text-warnink">{c.reason}</span> : null}
              </span>
              <span className="col-start-2 row-span-3 row-start-1 w-16 text-right sm:col-start-auto sm:row-span-1 sm:row-start-auto">
                {c ? (
                  <span className={`inline-flex items-center gap-1 text-[12px] font-semibold ${c.agrees ? "text-goodink" : "text-warnink"}`} title={c.reason}>
                    {c.agrees ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> : <TriangleAlert className="h-3.5 w-3.5" aria-hidden />}
                    {c.agrees ? t("try.agrees") : t("try.check")}
                  </span>
                ) : (
                  <CircleDashed className="ml-auto h-3.5 w-3.5 text-muted" aria-hidden />
                )}
              </span>
            </motion.button>
            <AnimatePresence initial={false}>
              {sel === f.id && c?.crop_box && run.image && (
                <motion.div className="overflow-hidden bg-accent/5" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25, ease: EASE }}>
                  <div className="flex flex-wrap items-center gap-3 px-4 pb-3">
                    <div className="w-[min(260px,100%)]"><CropView src={run.image} box={c.crop_box} alt={`${f.label}: ${t("try.crop_seen")}`} imgAspect={aspect} /></div>
                    <p className="min-w-[140px] flex-1 text-[12px] text-ink2"><ScanEye className="mr-1 inline h-3.5 w-3.5 text-accent" aria-hidden />{t("try.crop_seen")}</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            </div>
          );
        })}
      </div>
      {run.done?.unchecked ? <p className="border-t border-line px-4 py-2 text-[12px] text-muted">{t("try.unchecked", { n: run.done.unchecked })}</p> : null}
    </div>
  );
}

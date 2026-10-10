import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Mic, Square, X } from "lucide-react";
import { api } from "@/lib/api";
import { useProject } from "@/lib/project";

const FIELD: Record<string, string> = { al: "produced_t", rod_mass: "rod_consumed_t", scrap: "scrap_t" };
const LANGS = [
  { code: "hi", label: "हिंदी" },
  { code: "pa", label: "ਪੰਜਾਬੀ" },
  { code: "ta", label: "தமிழ்" },
  { code: "en", label: "English" },
];
const MAX_SECONDS = 30;

/** X1: answer a gap question by voice. The value is stored with the audio and transcript and
 *  waits for a human confirmation (amber) before it counts as approved. */
export function VoiceAnswer({ kind, process, missing }: { kind: string; process: string; missing: string[] }) {
  const { t, i18n } = useTranslation();
  const { pid, bundle, refresh } = useProject();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const [open, setOpen] = useState(false);
  const months = bundle?.project.months ?? [];
  const [month, setMonth] = useState(missing[0] ?? months[months.length - 1] ?? "");
  const [lang, setLang] = useState(["hi", "pa", "ta"].includes(i18n.language) ? i18n.language : "hi");
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [secs, setSecs] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const live = !!health.data?.models?.gemini_configured;
  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);
  if (!FIELD[kind]) return null;

  async function start() {
    setMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        if (timer.current) window.clearInterval(timer.current);
        const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
        setBusy(true);
        try {
          const fd = new FormData();
          fd.append("audio", blob, "voice.webm");
          fd.append("field_key", FIELD[kind]);
          fd.append("process", process);
          fd.append("period", month);
          fd.append("lang", lang);
          const r = await fetch(`/api/projects/${pid}/voice`, { method: "POST", body: fd });
          const j = await r.json();
          if (!r.ok) throw new Error(j.detail || r.statusText);
          setMsg(j.evidence ? `${t("voice.heard", { defaultValue: "Heard" })}: “${j.transcript}” → ${j.evidence.value_num} t` : `“${j.transcript}” — ${t("voice.none", { defaultValue: "no quantity found" })}`);
          await refresh();
        } catch (e) {
          setMsg((e as Error).message);
        } finally {
          setBusy(false);
          setRec(null);
        }
      };
      mr.start();
      setRec(mr);
      setSecs(0);
      timer.current = window.setInterval(() => {
        setSecs((s) => {
          if (s + 1 >= MAX_SECONDS) mr.state === "recording" && mr.stop();
          return s + 1;
        });
      }, 1000);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  if (!open)
    return (
      <button className="btn-quiet" onClick={() => setOpen(true)} disabled={!live} title={live ? t("voice.answer", { defaultValue: "Answer by voice" }) : t("voice.needs_live", { defaultValue: "Voice answers need live Gemini (not configured on this server)" })} aria-label={t("voice.answer", { defaultValue: "Answer by voice" })}>
        <Mic className="h-4 w-4" />
      </button>
    );
  return (
    <div className="mt-2 flex w-full flex-wrap items-center gap-2 rounded-xl border border-line bg-sunk p-2 text-[13px]">
      <select value={month} onChange={(e) => setMonth(e.target.value)} className="min-h-[36px] rounded-lg border border-line2 bg-surface px-2" aria-label="Month">
        {months.map((m) => (
          <option key={m} value={m}>
            {m}
            {missing.includes(m) ? " •" : ""}
          </option>
        ))}
      </select>
      <select value={lang} onChange={(e) => setLang(e.target.value)} className="min-h-[36px] rounded-lg border border-line2 bg-surface px-2" aria-label="Spoken language">
        {LANGS.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
      {!rec ? (
        <button className="btn-primary h-9 min-h-0" onClick={start} disabled={busy || !month}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />} {t("voice.record", { defaultValue: "Record" })}
        </button>
      ) : (
        <button className="btn-primary h-9 min-h-0 bg-bad" onClick={() => rec.stop()}>
          <Square className="h-4 w-4" /> {t("voice.stop", { defaultValue: "Stop" })} · {MAX_SECONDS - secs}s
        </button>
      )}
      <button className="btn-quiet h-9 min-h-0" onClick={() => setOpen(false)} aria-label={t("common.close")}>
        <X className="h-4 w-4" />
      </button>
      {msg && <div className="w-full text-ink2">{msg}</div>}
    </div>
  );
}

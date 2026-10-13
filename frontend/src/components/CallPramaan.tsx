import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { AlertTriangle, Keyboard, Loader2, Mic, MicOff, Phone, PhoneOff, ScanSearch, SendHorizonal, X } from "lucide-react";
import { useProject } from "@/lib/project";
import { CALL_LANGS, CallClient, callSupported, type CallEvent, type CallFigure } from "@/lib/call";
import { EASE, rise, stagger } from "@/lib/motion";
import { loadLanguage } from "@/i18n";
import { useLens } from "./EvidenceLens";

type Phase = "idle" | "connecting" | "live" | "ended" | "error";
interface Turn { who: "caller" | "agent"; text: string; open: boolean; figures?: CallFigure[]; unverified?: string[]; cut?: boolean }

const CallCtx = createContext<() => void>(() => {});
/** Open the "Call Pramaan" panel. */
export const useCall = () => useContext(CallCtx);

const TRY = ["try_save", "try_why", "try_show", "try_left"] as const;
// Punjabi is a call language but not a UI language, so its examples live here.
const PA_TRY: Record<(typeof TRY)[number], string> = {
  try_save: "ਮੇਰਾ ਡਾਟਾ ਮੇਰੇ ਖਰੀਦਦਾਰ ਦਾ ਸਾਲ ਵਿੱਚ ਕਿੰਨਾ ਬਚਾਉਂਦਾ ਹੈ?",
  try_why: "ਮੇਰੇ ਸਟੇਨਲੈਸ ਬੋਲਟਾਂ ਦਾ SEE ਇੰਨਾ ਜ਼ਿਆਦਾ ਕਿਉਂ ਹੈ?",
  try_show: "ਗੈਸ ਵਾਲਾ ਅੰਕੜਾ ਕਿੱਥੋਂ ਆਇਆ, ਦਿਖਾਓ।",
  try_left: "ਹੁਣ ਮੈਨੂੰ ਹੋਰ ਕੀ ਕਰਨਾ ਬਾਕੀ ਹੈ?",
};
const TOOL_KEY: Record<string, string> = {
  explain_number: "tool_explain",
  open_evidence: "tool_show",
  search_guidance: "tool_guidance",
  open_items: "tool_items",
};

/** Call Pramaan: talk to your report like a phone call, in English, Hindi, Punjabi, Tamil or
 *  Vietnamese. Gemini Live answers from the engine's figures; every figure it says appears here and
 *  opens the Evidence Lens, and it can open the lens itself ("show me where that comes from"). */
export function CallProvider({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const { pid, result } = useProject();
  const lens = useLens();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [err, setErr] = useState<string | null>(null);
  const [lang, setLang] = useState<string>(CALL_LANGS.some((l) => l.code === i18n.language) ? i18n.language : "en");
  const [, setLoaded] = useState(0);
  useEffect(() => {
    // the examples are shown in the call's language, which may not be the page's
    if (lang !== "pa") void loadLanguage(lang).then(() => setLoaded((n) => n + 1)).catch(() => undefined);
  }, [lang]);
  const example = (k: (typeof TRY)[number]) => (lang === "pa" ? PA_TRY[k] : t(`call.${k}`, { lng: lang }));
  const [turns, setTurns] = useState<Turn[]>([]);
  const [speaking, setSpeaking] = useState(false);
  const [tool, setTool] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [typing, setTyping] = useState(false);
  const [q, setQ] = useState("");
  const [secs, setSecs] = useState(0);
  const [limit, setLimit] = useState(300);
  const client = useRef<CallClient | null>(null);
  const ring = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const started = useRef(0);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [turns, reduce]);
  useEffect(() => {
    if (phase !== "live") return;
    const id = window.setInterval(() => setSecs(Math.floor((Date.now() - started.current) / 1000)), 500);
    return () => window.clearInterval(id);
  }, [phase]);
  useEffect(() => () => client.current?.hangup(), []);

  const onEvent = useCallback(
    (e: CallEvent) => {
      if (e.type === "ready") {
        setPhase("live");
        setLimit(e.max_seconds);
        started.current = Date.now();
      } else if (e.type === "caption") {
        setTurns((xs) => {
          const last = xs[xs.length - 1];
          if (last && last.who === e.who && last.open) return [...xs.slice(0, -1), { ...last, text: last.text + e.text }];
          // a new speaker closes the other side's open turn
          return [...xs.map((x) => (x.open ? { ...x, open: false } : x)), { who: e.who, text: e.text, open: true }];
        });
        if (e.who === "agent") setTool(null);
      } else if (e.type === "turn") {
        setTurns((xs) => {
          // the figures belong to the latest agent turn that has none yet
          const i = [...xs].reverse().findIndex((x) => x.who === "agent" && !x.figures);
          if (i < 0) return xs;
          const k = xs.length - 1 - i;
          return xs.map((x, j) => (j === k ? { ...x, open: false, figures: e.figures, unverified: e.unverified } : x));
        });
      } else if (e.type === "interrupted") {
        setTurns((xs) => xs.map((x, j) => (j === xs.length - 1 && x.who === "agent" ? { ...x, cut: true, open: false } : x)));
      } else if (e.type === "tool") {
        setTool(e.name);
      } else if (e.type === "action" && e.name === "open_evidence") {
        lens.open(e.node);
      } else if (e.type === "ended") {
        setPhase((p) => (p === "error" ? p : "ended"));
        if (e.reason !== "closed" && e.reason !== "hangup") setErr(`ended_${e.reason}`);
        client.current = null;
      } else if (e.type === "error") {
        setPhase("error");
        setErr(e.code);
        client.current?.hangup();
        client.current = null;
      }
    },
    [lens],
  );

  const start = useCallback(async () => {
    if (!callSupported()) {
      setPhase("error");
      setErr("unsupported");
      return;
    }
    setErr(null);
    setTurns([]);
    setSecs(0);
    setMuted(false);
    setPhase("connecting");
    const c = new CallClient(
      onEvent,
      (who, level) => {
        // the ring follows whoever is talking; no React render per audio frame
        const el = ring.current;
        if (el && (who === "agent" || !el.dataset.agent)) el.style.setProperty("--lvl", String(Math.min(1, level * (who === "caller" ? 6 : 3))));
      },
      (s) => {
        setSpeaking(s);
        if (ring.current) ring.current.dataset.agent = s ? "1" : "";
      },
    );
    client.current = c;
    try {
      await c.start(pid, lang);
    } catch (e) {
      client.current = null;
      setPhase("error");
      setErr((e as Error).message === "mic_denied" ? "mic_denied" : "call_failed");
    }
  }, [lang, onEvent, pid]);

  const hangup = useCallback(() => {
    client.current?.hangup();
    client.current = null;
    setPhase((p) => (p === "live" || p === "connecting" ? "ended" : p));
    setSpeaking(false);
    setTool(null);
  }, []);

  const openCall = useCallback(() => setOpen(true), []);
  const live = phase === "live" || phase === "connecting";
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const status = phase === "connecting" ? t("call.connecting") : tool ? t(`call.${TOOL_KEY[tool] ?? "tool_explain"}`) : speaking ? t("call.speaking") : muted ? t("call.muted") : t("call.listening");

  return (
    <CallCtx.Provider value={openCall}>
      {children}
      {result && (
        <AnimatePresence>
          {!open && (
            <motion.button
              key="call-fab"
              className="fixed bottom-[76px] right-5 z-20 inline-flex min-h-[48px] items-center gap-2 rounded-full border border-line2 bg-surface px-4 text-sm font-semibold text-ink shadow-lift transition hover:border-good/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-page"
              initial={{ opacity: 0, y: 16, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.9 }}
              transition={{ type: "spring", stiffness: 420, damping: 30, delay: 0.05 }}
              onClick={openCall}
              data-testid="call-fab"
            >
              <span className="grid h-6 w-6 place-items-center rounded-full bg-good text-white">
                <Phone className="h-3.5 w-3.5" aria-hidden />
              </span>
              {t("call.fab")}
            </motion.button>
          )}
        </AnimatePresence>
      )}
      <Dialog.Root
        open={open}
        onOpenChange={(o) => {
          if (!o) hangup();
          setOpen(o);
        }}
        modal={false}
      >
        <Dialog.Portal>
          <Dialog.Content
            onInteractOutside={(e) => e.preventDefault()}
            onEscapeKeyDown={(e) => live && e.preventDefault()}
            className="fixed inset-y-0 right-0 z-30 flex w-full max-w-[440px] flex-col border-l border-line bg-page shadow-lift focus:outline-none data-[state=closed]:animate-sheetout data-[state=open]:animate-sheet"
            aria-describedby="call-lead"
          >
            <div className="flex items-start gap-3 border-b border-line px-4 py-3">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-good text-white">
                <Phone className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <Dialog.Title className="font-semibold">{t("call.title")}</Dialog.Title>
                <p id="call-lead" className="text-[12px] text-muted">{t("call.lead")}</p>
              </div>
              <Dialog.Close className="btn-quiet" aria-label={live ? t("call.end") : t("common.close")}>
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>

            {(phase === "idle" || ((phase === "ended" || phase === "error") && !turns.length)) && (
              <motion.div className="flex-1 space-y-5 overflow-y-auto px-4 py-5" variants={stagger(0.05)} initial="hidden" animate="show">
                {err && <ErrorNote code={err} />}
                <motion.div variants={rise}>
                  <div className="eyebrow mb-2">{t("call.language")}</div>
                  <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t("call.language")}>
                    {CALL_LANGS.map((l) => (
                      <button
                        key={l.code}
                        role="radio"
                        aria-checked={lang === l.code}
                        onClick={() => setLang(l.code)}
                        className={`min-h-[44px] rounded-xl border px-3.5 text-[15px] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${lang === l.code ? "border-ink bg-ink text-page" : "border-line2 bg-surface text-ink hover:border-ink/40"}`}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                </motion.div>
                <motion.div variants={rise}>
                  <div className="eyebrow mb-2">{t("call.try")}</div>
                  <ul className="space-y-1.5 text-[14px] text-ink2">
                    {TRY.map((k) => (
                      <li key={k} className="flex gap-2 rounded-xl border border-line bg-surface px-3 py-2 shadow-card">
                        <span aria-hidden className="text-muted">“</span>
                        <span lang={lang}>{example(k)}</span>
                        <span aria-hidden className="text-muted">”</span>
                      </li>
                    ))}
                  </ul>
                </motion.div>
                <motion.p variants={rise} className="text-[12px] leading-relaxed text-muted">{t("call.privacy")}</motion.p>
              </motion.div>
            )}

            {(phase === "connecting" || phase === "live" || ((phase === "ended" || phase === "error") && turns.length > 0)) && (
              <>
                {live && (
                  <div className="flex flex-col items-center gap-2 border-b border-line bg-surface px-4 py-5">
                    <div
                      ref={ring}
                      className="call-ring relative grid h-24 w-24 place-items-center rounded-full"
                      data-reduce={reduce ? "1" : ""}
                      style={{ ["--lvl" as string]: 0 }}
                      aria-hidden
                    >
                      <span className={`grid h-16 w-16 place-items-center rounded-full ${speaking ? "bg-ink text-[#7dd3a8]" : "bg-good text-white"}`}>
                        {phase === "connecting" ? <Loader2 className="h-6 w-6 animate-spin" /> : speaking ? <span className="font-display text-lg font-semibold">P</span> : muted ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
                      </span>
                    </div>
                    <div className="text-sm font-semibold" role="status" aria-live="polite">{status}</div>
                    {phase === "live" && (
                      <div className="font-mono text-[12px] text-muted">
                        {mmss(secs)} / {mmss(limit)} · {CALL_LANGS.find((l) => l.code === lang)?.label}
                      </div>
                    )}
                  </div>
                )}
                <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite" aria-label={t("call.transcript")}>
                  {phase === "ended" && (
                    <div className="rounded-xl border border-line bg-sunk px-3 py-2 text-[13px] text-ink2">
                      {t("call.ended", { time: mmss(secs) })}
                      {err && <span className="block text-muted">{t(`call.err_${err}`)}</span>}
                    </div>
                  )}
                  {phase === "error" && err && <ErrorNote code={err} />}
                  {turns.map((x, i) => (
                    <TurnView key={i} turn={x} />
                  ))}
                  <div ref={end} />
                </div>
              </>
            )}

            <div className="border-t border-line p-3">
              {live ? (
                <div className="space-y-2">
                  {typing && (
                    <form
                      className="flex gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const text = q.trim();
                        if (!text) return;
                        client.current?.sendText(text);
                        setTurns((xs) => [...xs.map((x) => (x.open ? { ...x, open: false } : x)), { who: "caller", text, open: false }]);
                        setQ("");
                      }}
                    >
                      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder={t("call.type_placeholder")} aria-label={t("call.type_placeholder")} className="input min-w-0 flex-1 text-[15px]" />
                      <button className="btn-primary" disabled={!q.trim() || phase !== "live"} aria-label={t("copilot.ask")}>
                        <SendHorizonal className="h-4 w-4" />
                      </button>
                    </form>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      className={`btn-ghost flex-1 ${muted ? "border-warn/50 bg-warnbg text-warnink" : ""}`}
                      aria-pressed={muted}
                      disabled={phase !== "live"}
                      onClick={() => {
                        client.current?.setMuted(!muted);
                        setMuted(!muted);
                      }}
                    >
                      {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />} {muted ? t("call.unmute") : t("call.mute")}
                    </button>
                    <button className="btn-ghost" aria-pressed={typing} aria-label={t("call.type")} title={t("call.type")} onClick={() => setTyping(!typing)}>
                      <Keyboard className="h-4 w-4" />
                    </button>
                    <button className="btn flex-1 bg-bad text-white hover:brightness-110" onClick={hangup} data-testid="call-end">
                      <PhoneOff className="h-4 w-4" /> {t("call.end")}
                    </button>
                  </div>
                </div>
              ) : (
                <button className="btn w-full bg-good text-white shadow-cta hover:brightness-110" onClick={() => void start()} data-testid="call-start">
                  <Phone className="h-4 w-4" /> {phase === "idle" ? t("call.start") : t("call.again")}
                </button>
              )}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </CallCtx.Provider>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const { t } = useTranslation();
  if (turn.who === "caller")
    return (
      <motion.div className="ml-auto w-fit max-w-[88%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-[14px] text-page" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
        {turn.text}
      </motion.div>
    );
  return (
    <motion.div className="space-y-2" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
      <div className="w-fit max-w-[92%] rounded-2xl rounded-bl-md border border-line bg-surface px-3.5 py-2 text-[14px] leading-relaxed shadow-card">
        {turn.text}
        {turn.cut && <span className="ml-1 text-[12px] text-muted">({t("call.cut")})</span>}
      </div>
      {!!turn.figures?.length && (
        <motion.ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface" variants={stagger(0.06)} initial="hidden" animate="show" aria-label={t("call.figures")}>
          {turn.figures.map((f) => (
            <motion.li key={f.id} variants={rise}>
              <Figure f={f} />
            </motion.li>
          ))}
        </motion.ul>
      )}
      {!!turn.unverified?.length && (
        <p className="flex items-start gap-2 rounded-xl border border-warn/40 bg-warnbg px-3 py-2 text-[12px] text-warnink">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {t("call.unverified", { list: turn.unverified.join(", ") })}
        </p>
      )}
    </motion.div>
  );
}

function Figure({ f }: { f: CallFigure }) {
  const { open } = useLens();
  const body = (
    <>
      <span className="min-w-0 flex-1 text-[12px] text-ink2">{f.label}</span>
      <span className="num shrink-0 font-mono text-[13px] font-medium text-ink">
        {f.value}
        {f.unit && f.unit !== "-" ? <span className="ml-1 font-sans text-[10px] text-muted">{f.unit}</span> : null}
      </span>
      {f.node && <ScanSearch className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />}
    </>
  );
  return f.node ? (
    <button type="button" onClick={() => open(f.node!)} className="flex w-full items-center gap-3 px-3 py-2 text-left transition hover:bg-sunk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/60">
      {body}
    </button>
  ) : (
    <div className="flex items-center gap-3 px-3 py-2">{body}</div>
  );
}

function ErrorNote({ code }: { code: string }) {
  const { t } = useTranslation();
  return (
    <p className="flex items-start gap-2 rounded-xl border border-bad/30 bg-badbg px-3 py-2 text-[13px] text-badink" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      {t(`call.err_${code}`, { defaultValue: t("call.err_call_failed") })}
    </p>
  );
}

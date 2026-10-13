import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowLeft, ArrowRight, BadgeCheck, Compass, X } from "lucide-react";
import { EASE } from "@/lib/motion";

/** One stop: which workspace step it lives on and which element it lights up (none = centred card). */
interface Stop { key: string; step: "report" | "gaps"; target?: string }
const STOPS: Stop[] = [
  { key: "verdict", step: "report", target: '[data-tour="verdict"]' },
  { key: "see", step: "report", target: '[data-tour="see"]' },
  { key: "review", step: "gaps", target: '[data-tour="review"]' },
  { key: "letter", step: "report", target: '[data-tour="letter"]' },
  { key: "pulse", step: "report", target: "#pulse" },
  { key: "ask", step: "report", target: '[data-tour="ask"]' },
  { key: "call", step: "report", target: '[data-testid="call-fab"]' },
  { key: "proof", step: "report" },
];

const TourCtx = createContext<() => void>(() => {});
/** Start the 90-second tour of the sample factory. */
export const useTour = () => useContext(TourCtx);

interface Box { top: number; left: number; width: number; height: number }

/** A short guided tour for people with two minutes (judges): a spotlight on each part of the
 *  product that matters, in order, with one sentence on why. Esc or Skip ends it; reduced motion
 *  turns the glides into cuts. Starts from ?tour=1 (the landing page) or the workspace header. */
export function TourProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { pid = "", step = "report" } = useParams();
  const [params, setParams] = useSearchParams();
  const [i, setI] = useState<number | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const reduce = useReducedMotion();

  const start = useCallback(() => setI(0), []);
  useEffect(() => {
    if (params.get("tour") === "1") {
      params.delete("tour");
      setParams(params, { replace: true });
      setI(0);
    }
  }, [params, setParams]);

  const stop = i === null ? null : STOPS[i];
  // go to the stop's page, then find its element, bring it into view and measure it
  useEffect(() => {
    if (!stop) return;
    if (stop.step !== step) {
      nav(`/p/${pid}/${stop.step}`);
      return;
    }
    setBox(null);
    if (!stop.target) return;
    let tries = 0;
    let raf = 0;
    const find = () => {
      const el = document.querySelector<HTMLElement>(stop.target!);
      if (!el) {
        if (tries++ < 120) raf = requestAnimationFrame(find);
        return;
      }
      el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
      window.setTimeout(() => measure(el), reduce ? 50 : 450);
    };
    const measure = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      setBox({ top: r.top - 8, left: r.left - 8, width: r.width + 16, height: r.height + 16 });
    };
    find();
    const onMove = () => {
      const el = document.querySelector<HTMLElement>(stop.target!);
      if (el) measure(el);
    };
    window.addEventListener("scroll", onMove, { passive: true });
    window.addEventListener("resize", onMove);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onMove);
      window.removeEventListener("resize", onMove);
    };
  }, [stop, step, pid, nav, reduce]);

  useEffect(() => {
    if (i === null) return;
    next.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setI(null);
      if (e.key === "ArrowRight") setI((x) => (x === null ? x : Math.min(x + 1, STOPS.length - 1)));
      if (e.key === "ArrowLeft") setI((x) => (x === null ? x : Math.max(x - 1, 0)));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [i]);

  // the card sits below the spotlight when there is room, else above; centred when there is no target
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  useLayoutEffect(() => {
    const c = card.current;
    if (!c || i === null) return;
    const w = c.offsetWidth;
    const h = c.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (!box) {
      setPos({ top: Math.max(16, (vh - h) / 2), left: Math.max(16, (vw - w) / 2) });
      return;
    }
    const below = box.top + box.height + 12;
    const top = below + h < vh - 12 ? below : box.top - h - 12 >= 12 ? box.top - h - 12 : Math.max(12, vh - h - 12);
    const left = Math.min(Math.max(12, box.left + box.width / 2 - w / 2), vw - w - 12);
    setPos({ top, left });
  }, [box, i]);

  const last = i === STOPS.length - 1;
  return (
    <TourCtx.Provider value={start}>
      {children}
      <AnimatePresence>
        {stop && (
          // below the Ask panel (z-30) and the Evidence Lens (z-40/50): what the tour points at can be opened over it
          <motion.div key="tour" className="pointer-events-none fixed inset-0 z-[25]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            {/* the dim with a hole: one element with a huge shadow, so the lit area stays clickable */}
            {box ? (
              <motion.div
                className="pointer-events-none fixed rounded-2xl ring-2 ring-accent/70"
                style={{ boxShadow: "0 0 0 9999px rgba(10, 14, 22, 0.55)" }}
                initial={false}
                animate={{ top: box.top, left: box.left, width: box.width, height: box.height }}
                transition={reduce ? { duration: 0 } : { duration: 0.45, ease: EASE }}
                aria-hidden
              />
            ) : (
              <div className="pointer-events-none fixed inset-0 bg-[rgba(10,14,22,0.55)]" aria-hidden />
            )}
            <motion.div
              ref={card}
              role="dialog"
              aria-modal="false"
              aria-labelledby="tour-title"
              aria-describedby="tour-body"
              className="pointer-events-auto fixed w-[min(380px,calc(100vw-24px))] rounded-2xl border border-line bg-page p-4 shadow-lift"
              initial={false}
              animate={{ top: pos.top, left: pos.left }}
              transition={reduce ? { duration: 0 } : { duration: 0.35, ease: EASE }}
            >
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-accent" aria-hidden />
                <span className="eyebrow">{t("tour.eyebrow", { n: i! + 1, total: STOPS.length })}</span>
                <button className="btn-quiet ml-auto min-h-[32px] px-2" onClick={() => setI(null)} aria-label={t("tour.end")}>
                  <X className="h-4 w-4" />
                </button>
              </div>
              <AnimatePresence mode="wait">
                <motion.div key={stop.key} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.2 }}>
                  <h2 id="tour-title" className="mt-1 text-[17px] font-semibold leading-snug">{t(`tour.${stop.key}_t`)}</h2>
                  <p id="tour-body" className="mt-1 text-[14px] text-ink2">{t(`tour.${stop.key}_d`)}</p>
                </motion.div>
              </AnimatePresence>
              <div className="mt-4 flex items-center gap-2">
                <div className="flex gap-1" aria-hidden>
                  {STOPS.map((s, k) => (
                    <span key={s.key} className={`h-1.5 rounded-full transition-all duration-300 ${k === i ? "w-4 bg-accent" : "w-1.5 bg-line2"}`} />
                  ))}
                </div>
                <div className="ml-auto flex gap-2">
                  {i! > 0 && (
                    <button className="btn-ghost min-h-[36px] px-3" onClick={() => setI(i! - 1)} aria-label={t("common.back")}>
                      <ArrowLeft className="h-4 w-4" />
                    </button>
                  )}
                  {last ? (
                    <button
                      ref={next}
                      className="btn-primary min-h-[36px] px-3"
                      onClick={() => {
                        setI(null);
                        nav("/proof");
                      }}
                    >
                      <BadgeCheck className="h-4 w-4" /> {t("tour.proof_cta")}
                    </button>
                  ) : (
                    <button ref={next} className="btn-primary min-h-[36px] px-3" onClick={() => setI(i! + 1)}>
                      {t("tour.next")} <ArrowRight className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </TourCtx.Provider>
  );
}

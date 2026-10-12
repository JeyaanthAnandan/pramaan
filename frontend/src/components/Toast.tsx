import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, Info, TriangleAlert } from "lucide-react";
import { EASE } from "@/lib/motion";

type Tone = "good" | "info" | "warn";
interface Item { id: number; tone: Tone; text: string }

const Ctx = createContext<(text: string, tone?: Tone) => void>(() => {});
/** Short confirmation that an action took effect ("Approved 15.4 — report recalculated"). */
export const useToast = () => useContext(Ctx);

const ICON = { good: CheckCircle2, info: Info, warn: TriangleAlert };
const COLOR = { good: "text-good", info: "text-accent", warn: "text-warn" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const seq = useRef(0);
  const push = useCallback((text: string, tone: Tone = "good") => {
    const id = ++seq.current;
    setItems((xs) => [...xs.slice(-2), { id, tone, text }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 3800);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[70] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:left-auto sm:right-6 sm:items-end">
        <AnimatePresence initial={false}>
          {items.map((x) => {
            const Icon = ICON[x.tone];
            return (
              <motion.div
                key={x.id}
                layout
                initial={{ opacity: 0, y: 18, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.98, transition: { duration: 0.18 } }}
                transition={{ duration: 0.32, ease: EASE }}
                className="pointer-events-auto flex max-w-[min(420px,calc(100vw-2rem))] items-start gap-2.5 rounded-xl border border-line bg-surface/95 px-4 py-3 text-[13px] font-medium text-ink shadow-lift backdrop-blur"
              >
                <Icon className={`mt-px h-4 w-4 shrink-0 ${COLOR[x.tone]}`} aria-hidden />
                <span>{x.text}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}

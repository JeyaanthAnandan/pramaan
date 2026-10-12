// Motion language: values are *read* (scan), *verified* (stamp), *computed* (numbers settle into
// place) and *flow* (the agent pipeline). Short durations, one easing curve, and everything
// respects prefers-reduced-motion (MotionConfig reducedMotion="user" + the checks below).
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { animate, motion, useInView, useReducedMotion, type Variants } from "motion/react";

export const EASE = [0.2, 0.7, 0.2, 1] as const;
export const DUR = { fast: 0.15, base: 0.25, slow: 0.45, count: 1.1 };
export const SPRING = { type: "spring", stiffness: 520, damping: 40, mass: 0.8 } as const;

/** A number that settles into place. By default it only tweens when the value changes (a lever,
 *  an approval); with `countUp` it also counts up the first time it scrolls into view. The final
 *  text is always exactly `format(value)`. */
export function AnimatedNumber({ value, format, countUp = false, from = 0, duration, className }: {
  value: number | string | null | undefined;
  format: (v: number) => string;
  countUp?: boolean;
  from?: number;
  duration?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const target = value === null || value === undefined || value === "" ? NaN : Number(value);
  const ok = Number.isFinite(target);
  const shown = useRef<number>(countUp && !reduce ? from : target);
  const started = useRef(!countUp || !!reduce);
  const [text, setText] = useState(() => (ok ? format(shown.current) : "—"));
  const fmt = useRef(format);
  fmt.current = format;

  useEffect(() => {
    if (!ok) {
      setText("—");
      return;
    }
    if (!started.current && !inView) return;
    const first = !started.current;
    started.current = true;
    const start = shown.current;
    if (reduce || start === target || !Number.isFinite(start)) {
      shown.current = target;
      setText(fmt.current(target));
      return;
    }
    const controls = animate(start, target, {
      duration: duration ?? (first ? DUR.count : 0.6),
      ease: EASE,
      onUpdate: (v) => {
        shown.current = v;
        setText(fmt.current(v));
      },
      onComplete: () => {
        shown.current = target;
        setText(fmt.current(target));
      },
    });
    return () => controls.stop();
  }, [target, ok, inView, reduce, duration]);

  return (
    <span ref={ref} className={`num ${className ?? ""}`}>
      {text}
    </span>
  );
}

/** Fade-and-rise when the block first scrolls into view (landing and reference pages only). */
export function Reveal({ children, className, delay = 0, y = 14 }: { children: ReactNode; className?: string; delay?: number; y?: number }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: DUR.slow, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Children enter one after another, in reading order. */
export const stagger = (gap = 0.06, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});
export const rise: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: DUR.slow, ease: EASE } },
};

// literal class names, so Tailwind keeps them
const STAMP_TONE = { good: "stamp-good", warn: "stamp-warn", accent: "stamp-accent" } as const;

/** A rubber stamp pressed onto the page: the "Mill Certificate" way of saying verified/approved. */
export function Stamp({ children, tone = "good", className = "", delay = 0 }: { children: ReactNode; tone?: "good" | "warn" | "accent"; className?: string; delay?: number }) {
  return (
    <motion.span
      className={`stamp ${STAMP_TONE[tone]} ${className}`}
      initial={{ opacity: 0, scale: 1.9, rotate: -16 }}
      animate={{ opacity: 1, scale: 1, rotate: -6 }}
      transition={{ type: "spring", stiffness: 560, damping: 24, mass: 0.7, delay }}
    >
      {children}
    </motion.span>
  );
}

interface SegOption<T extends string> { value: T; label: ReactNode; icon?: ReactNode }

/** Segmented control with a sliding indicator. `role="tab"` keeps tab semantics (arrow keys move). */
export function Segmented<T extends string>({ value, onChange, options, role = "tab", label, size = "md", className = "" }: {
  value: T;
  onChange: (v: T) => void;
  options: SegOption<T>[];
  role?: "tab" | "toggle";
  label?: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const id = useId();
  const btns = useRef<(HTMLButtonElement | null)[]>([]);
  function onKey(e: KeyboardEvent, i: number) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const j = (i + (e.key === "ArrowRight" ? 1 : -1) + options.length) % options.length;
    onChange(options[j].value);
    btns.current[j]?.focus();
  }
  const pad = size === "sm" ? "min-h-[32px] px-2.5 text-[12px]" : "min-h-[36px] px-3 text-[13px]";
  return (
    <div role={role === "tab" ? "tablist" : "group"} aria-label={label} className={`relative inline-flex max-w-full rounded-xl border border-line bg-sunk p-1 ${className}`}>
      {options.map((o, i) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => (btns.current[i] = el)}
            type="button"
            role={role === "tab" ? "tab" : undefined}
            aria-selected={role === "tab" ? on : undefined}
            aria-pressed={role === "toggle" ? on : undefined}
            tabIndex={role === "tab" && !on ? -1 : 0}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => role === "tab" && onKey(e, i)}
            className={`relative flex-1 whitespace-nowrap rounded-lg font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent/60 ${pad} ${on ? "text-ink" : "text-ink2 hover:text-ink"}`}
          >
            {on && <motion.span layoutId={`seg-${id}`} className="absolute inset-0 rounded-lg bg-surface shadow-card" transition={SPRING} aria-hidden />}
            <span className="relative inline-flex items-center justify-center gap-1.5">
              {o.icon}
              {o.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Height-animated disclosure body (lists that expand: passed checks, OK items, event logs). */
export function Collapse({ open, children, className }: { open: boolean; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.toggleAttribute("inert", !open); // closed content is not reachable by keyboard
  }, [open]);
  return (
    <motion.div
      ref={ref}
      initial={false}
      animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
      transition={{ duration: DUR.base, ease: EASE }}
      className={`overflow-hidden ${className ?? ""}`}
      aria-hidden={!open}
    >
      {children}
    </motion.div>
  );
}

/** True once, after `ms`; used to sequence small reveals (reader 1, then reader 2, then the verdict). */
export function useAfter(ms: number, deps: unknown[] = []): boolean {
  const reduce = useReducedMotion();
  const [on, setOn] = useState(!!reduce);
  useEffect(() => {
    if (reduce) {
      setOn(true);
      return;
    }
    setOn(false);
    const id = window.setTimeout(() => setOn(true), ms);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, reduce, ...deps]);
  return on;
}

/** How much a value just went up (for a few seconds after it rises), e.g. "+€163,002" when a
 *  supplier's verified data lands. Null otherwise, and on the first render. */
export function useRise(value: number, ms = 4500): number | null {
  const prev = useRef<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);
  useEffect(() => {
    const before = prev.current;
    prev.current = value;
    if (before === null || !(value > before + 0.5)) return;
    setDelta(value - before);
    const id = window.setTimeout(() => setDelta(null), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return delta;
}

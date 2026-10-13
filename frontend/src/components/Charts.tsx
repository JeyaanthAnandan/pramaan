import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { eur, inr } from "@/lib/format";
import { AnimatedNumber, EASE } from "@/lib/motion";
import { useLens } from "./EvidenceLens";

/* Chart rules (dataviz method): thin marks, 2px lines, >=8px markers with a 2px surface ring,
   hairline solid grid, one y-axis, legend for >=2 series plus selective direct labels,
   crosshair + tooltip on hover/focus, and a table view twin. Series colours were validated
   with the palette validator (light + dark, all pairs).
   Motion: marks grow from the baseline / draw left to right the first time they are seen (time
   flows 2026 -> 2034), and morph when an input changes, so the eye follows what moved. */

export function ReadinessRing({ value, size = 92, label, stroke = 8 }: { value: number; size?: number; label?: string; stroke?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const reduce = useReducedMotion();
  const r = (size - stroke - 4) / 2;
  const v = Math.max(0, Math.min(100, value));
  const sev = v >= 90 ? "var(--s1)" : v >= 60 ? "var(--warn)" : "var(--bad)";
  const shown = inView || reduce ? v / 100 : 0;
  return (
    <div ref={ref} className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${label ?? "Readiness"} ${v.toFixed(0)}%`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`rgb(${sev} / 0.16)`} strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`rgb(${sev})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          initial={{ pathLength: reduce ? v / 100 : 0, opacity: reduce ? 1 : 0 }}
          animate={{ pathLength: shown, opacity: shown > 0 ? 1 : 0 }}
          transition={{ pathLength: { duration: 1.1, ease: EASE }, opacity: { duration: 0.15 } }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center" aria-hidden>
        <AnimatedNumber value={v} format={(x) => `${x.toFixed(0)}%`} countUp className={`${size < 70 ? "text-[13px]" : size < 100 ? "text-xl" : "text-2xl"} font-semibold tracking-tight`} />
      </div>
    </div>
  );
}

export function ContributionBar({ segments }: { segments: { key: string; label: string; value: number; node: string; tag?: string }[] }) {
  const { open } = useLens();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const reduce = useReducedMotion();
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const color: Record<string, string> = { own: "var(--s3)", rod: "var(--s1)" };
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div>
      <div ref={ref} className="flex h-[22px] w-full gap-[2px]">
        {segments.map((s, i) => {
          const pct = Math.max((s.value / total) * 100, 1.2);
          return (
            <motion.button
              key={s.key}
              className={`relative h-full transition-opacity ${i === 0 ? "rounded-l-[4px]" : ""} ${i === segments.length - 1 ? "rounded-r-[4px]" : ""} ${hover && hover !== s.key ? "opacity-60" : ""}`}
              style={{ background: `rgb(${color[s.key] ?? "var(--line2)"})` }}
              initial={{ width: reduce ? `${pct}%` : "0%" }}
              animate={{ width: inView || reduce ? `${pct}%` : "0%" }}
              transition={{ duration: 0.9, ease: EASE, delay: i * 0.12 }}
              onMouseEnter={() => setHover(s.key)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(s.key)}
              onBlur={() => setHover(null)}
              onClick={() => open(s.node)}
              aria-label={`${s.label}: ${((s.value / total) * 100).toFixed(1)}%`}
            />
          );
        })}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink2">
        {segments.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: `rgb(${color[s.key] ?? "var(--line2)"})` }} aria-hidden />
            <span>{s.label}</span>
            <b className="num text-ink">{((s.value / total) * 100).toFixed(1)}%</b>
            {s.tag && <span className="text-muted">· {s.tag}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Two costs side by side, drawn to scale; the cheaper one is what the EU buyer pays. */
export function CostBars({ rows, pickLabel }: { rows: { key: string; label: string; value: number; color: string; display: ReactNode; sub?: ReactNode; pick: boolean }[]; pickLabel: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const reduce = useReducedMotion();
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div ref={ref} className="space-y-2.5">
      {rows.map((r, i) => {
        const w = `${Math.max((r.value / max) * 100, 1.5)}%`;
        return (
          <div key={r.key}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-[13px]">
              <span className={r.pick ? "font-medium text-ink" : "text-ink2"}>{r.label}</span>
              <span className={`num ${r.pick ? "font-semibold text-ink" : "text-muted"}`}>
                {r.display}
                {r.sub && <span className="ml-1.5 font-normal text-muted">{r.sub}</span>}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-sunk">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: `rgb(var(${r.color}))`, opacity: r.pick ? 1 : 0.38 }}
                  initial={{ width: reduce ? w : "0%" }}
                  animate={{ width: inView || reduce ? w : "0%" }}
                  transition={{ duration: 0.9, ease: EASE, delay: 0.1 + i * 0.12 }}
                />
              </div>
              <span className={`w-[88px] shrink-0 text-right text-[11px] font-semibold ${r.pick ? "text-ink" : "text-transparent"}`} aria-hidden={!r.pick}>
                {r.pick ? `✓ ${pickLabel}` : "·"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export interface Series {
  key: string;
  label: string;
  color: string; // css var name, e.g. "--s1"
  dashed?: boolean;
  points: { x: number; y: number; inr?: number; node?: string }[];
}

export function MoneyChart({ series, gapBetween, height = 300, ariaLabel, compact = false }: { series: Series[]; gapBetween?: [string, string]; height?: number; ariaLabel: string; compact?: boolean }) {
  const { t } = useTranslation();
  const { open } = useLens();
  const wrap = useRef<HTMLDivElement>(null);
  const inView = useInView(wrap, { once: true, amount: 0.35 });
  const reduce = useReducedMotion();
  const clip = `clip${useId().replace(/:/g, "")}`;
  const [hi, setHi] = useState<number | null>(null);
  const W = 720;
  const H = height;
  const pad = { l: 56, r: compact ? 78 : 92, t: 18, b: 34 };
  const xs = series[0]?.points.map((p) => p.x) ?? [];
  const maxY = Math.max(1, ...series.flatMap((s) => s.points.map((p) => p.y)));
  const niceMax = useMemo(() => {
    const step = Math.pow(10, Math.floor(Math.log10(maxY)));
    return Math.ceil((maxY * 1.08) / (step / 2)) * (step / 2);
  }, [maxY]);
  const ticks = useMemo(() => {
    const n = compact ? 4 : 5;
    return Array.from({ length: n + 1 }, (_, i) => (niceMax / n) * i);
  }, [niceMax, compact]);
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / Math.max(1, xs.length - 1);
  const y = (v: number) => pad.t + (1 - v / niceMax) * (H - pad.t - pad.b);
  const path = (s: Series) => s.points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");

  const gapArea = useMemo(() => {
    if (!gapBetween) return null;
    const top = series.find((s) => s.key === gapBetween[0]);
    const bot = series.find((s) => s.key === gapBetween[1]);
    if (!top || !bot) return null;
    if (top.points.some((p, i) => p.y < bot.points[i].y)) return null; // only when default is above actual everywhere
    const up = top.points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
    const down = [...bot.points].reverse().map((p, j) => `L${x(bot.points.length - 1 - j).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
    return `${up} ${down} Z`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, gapBetween, niceMax]);

  function onMove(clientX: number) {
    const el = wrap.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = ((clientX - rect.left) / rect.width) * W;
    let best = 0;
    xs.forEach((_, i) => {
      if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
    });
    setHi(best);
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowRight") setHi((h) => Math.min(xs.length - 1, (h ?? -1) + 1));
    if (e.key === "ArrowLeft") setHi((h) => Math.max(0, (h ?? xs.length) - 1));
  }

  const last = xs.length - 1;
  // end labels: avoid collisions by nudging, min 15px apart
  const ends = series.map((s) => ({ key: s.key, yy: y(s.points[last].y), v: s.points[last].y }));
  ends.sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) if (ends[i].yy - ends[i - 1].yy < 15) ends[i].yy = ends[i - 1].yy + 15;
  const drawn = inView || !!reduce;
  const morph = { duration: 0.55, ease: EASE };

  return (
    <div className="relative">
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink2">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <svg width="18" height="8" aria-hidden>
              <line x1="0" x2="18" y1="4" y2="4" stroke={`rgb(var(${s.color}))`} strokeWidth="2" strokeDasharray={s.dashed ? "4 3" : undefined} />
            </svg>
            {s.label}
          </li>
        ))}
      </ul>
      <div
        ref={wrap}
        className="relative w-full touch-pan-y rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        onMouseMove={(e) => onMove(e.clientX)}
        onMouseLeave={() => setHi(null)}
        onTouchMove={(e) => onMove(e.touches[0].clientX)}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={() => setHi((h) => h ?? 0)}
        onBlur={() => setHi(null)}
        role="img"
        aria-label={ariaLabel}
      >
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full">
          <defs>
            <clipPath id={clip}>
              <motion.rect x={0} y={0} height={H} initial={{ width: reduce ? W : 0 }} animate={{ width: drawn ? W : 0 }} transition={{ duration: 1.3, ease: EASE }} />
            </clipPath>
          </defs>
          {ticks.map((tv) => (
            <g key={tv}>
              <line x1={pad.l} x2={W - pad.r} y1={y(tv)} y2={y(tv)} stroke="rgb(var(--line))" strokeWidth={1} />
              <text x={pad.l - 8} y={y(tv)} textAnchor="end" dominantBaseline="middle" className="fill-muted" fontSize="11" style={{ fontVariantNumeric: "tabular-nums" }}>
                €{tv >= 1000 ? `${(tv / 1000).toFixed(tv % 1000 ? 1 : 0)}K` : tv.toFixed(0)}
              </text>
            </g>
          ))}
          <line x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} stroke="rgb(var(--line2))" strokeWidth={1} />
          {xs.map((xv, i) => (
            <text key={xv} x={x(i)} y={H - 12} textAnchor="middle" fontSize="11" className={hi === i ? "fill-ink" : "fill-muted"} style={{ fontVariantNumeric: "tabular-nums" }}>
              {xv}
            </text>
          ))}
          {hi !== null && <line x1={x(hi)} x2={x(hi)} y1={pad.t} y2={H - pad.b} stroke="rgb(var(--line2))" strokeWidth={1} />}
          <g clipPath={`url(#${clip})`}>
            <AnimatePresence>
              {gapArea && <motion.path key="gap" initial={{ opacity: 0, d: gapArea }} animate={{ opacity: 1, d: gapArea }} exit={{ opacity: 0 }} transition={morph} fill="rgb(var(--s2) / 0.10)" />}
            </AnimatePresence>
            <AnimatePresence>
              {series.map((s) => (
                <motion.path
                  key={s.key}
                  initial={{ opacity: 0, d: path(s) }}
                  animate={{ opacity: 1, d: path(s) }}
                  exit={{ opacity: 0 }}
                  transition={morph}
                  fill="none"
                  stroke={`rgb(var(${s.color}))`}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray={s.dashed ? "6 5" : undefined}
                />
              ))}
            </AnimatePresence>
            {series.map((s) =>
              s.points.map((p, i) =>
                i === 0 || i === last || hi === i ? (
                  <g key={`${s.key}${i}`} className="cursor-pointer" onClick={() => p.node && open(p.node)}>
                    <circle cx={x(i)} cy={y(p.y)} r={12} fill="transparent" />
                    <motion.circle initial={false} animate={{ cy: y(p.y) }} transition={morph} cx={x(i)} r={4.5} fill={`rgb(var(${s.color}))`} stroke="rgb(var(--surface))" strokeWidth={2} />
                  </g>
                ) : null,
              ),
            )}
          </g>
          <motion.g initial={{ opacity: reduce ? 1 : 0 }} animate={{ opacity: drawn ? 1 : 0 }} transition={{ duration: 0.3, delay: reduce ? 0 : 1.05 }}>
            {ends.map((e) => (
              <g key={e.key}>
                <line x1={x(last) + 6} x2={x(last) + 14} y1={y(series.find((s) => s.key === e.key)!.points[last].y)} y2={e.yy} stroke="rgb(var(--line2))" strokeWidth={1} />
                <text x={x(last) + 17} y={e.yy} dominantBaseline="middle" fontSize="12" fontWeight={600} className="fill-ink" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {eur(e.v)}
                </text>
              </g>
            ))}
          </motion.g>
        </svg>
        <AnimatePresence>
          {hi !== null && (
            <motion.div
              key="tip"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0, left: `${(x(hi) / W) * 100}%`, x: x(hi) / W > 0.6 ? "-105%" : "8px" }}
              exit={{ opacity: 0, transition: { duration: 0.1 } }}
              transition={{ duration: 0.18, ease: EASE }}
              className="pointer-events-none absolute top-2 z-10 min-w-[180px] rounded-xl border border-line bg-surface/95 px-3 py-2 text-[12px] shadow-lift backdrop-blur"
            >
              <div className="mb-1 font-semibold">{xs[hi]}</div>
              {series.map((s) => (
                <div key={s.key} className="flex items-center gap-2 py-0.5">
                  <svg width="12" height="6" aria-hidden>
                    <line x1="0" x2="12" y1="3" y2="3" stroke={`rgb(var(${s.color}))`} strokeWidth="2" strokeDasharray={s.dashed ? "3 2" : undefined} />
                  </svg>
                  <b className="num text-ink">{eur(s.points[hi].y)}</b>
                  {s.points[hi].inr !== undefined && <span className="num text-muted">{inr(s.points[hi].inr!)}</span>}
                  <span className="ml-auto pl-2 text-muted">{s.label}</span>
                </div>
              ))}
              <div className="mt-1 text-[10px] text-muted">{t("money.eur_t", { defaultValue: "€/t" })}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

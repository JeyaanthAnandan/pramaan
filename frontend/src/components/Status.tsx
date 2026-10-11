import { AlertTriangle, CheckCircle2, CircleDashed, FileQuestion, Info, ShieldCheck, Sigma, Sparkles, XCircle, BookMarked, FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";

// Colour carries status only, and always with an icon + a word (never colour alone).
type Tone = "good" | "warn" | "bad" | "neutral" | "info";

const MAP: Record<string, { tone: Tone; icon: typeof CheckCircle2 }> = {
  VERIFIED_2R: { tone: "good", icon: ShieldCheck },
  APPROVED: { tone: "warn", icon: CheckCircle2 },
  NEEDS_REVIEW: { tone: "warn", icon: AlertTriangle },
  PENDING: { tone: "warn", icon: CircleDashed },
  MISSING: { tone: "bad", icon: FileQuestion },
  DEFAULT_USED: { tone: "bad", icon: XCircle },
  ASSUMPTION: { tone: "info", icon: FlaskConical },
  REFDATA: { tone: "neutral", icon: BookMarked },
  CALCULATED: { tone: "neutral", icon: Sigma },
  SCENARIO: { tone: "info", icon: Sparkles },
  green: { tone: "good", icon: CheckCircle2 },
  amber: { tone: "warn", icon: AlertTriangle },
  red: { tone: "bad", icon: XCircle },
  info: { tone: "neutral", icon: Info },
  pass: { tone: "good", icon: CheckCircle2 },
  fail: { tone: "bad", icon: XCircle },
  warn: { tone: "warn", icon: AlertTriangle },
};

const TONE: Record<Tone, string> = {
  good: "bg-goodbg text-goodink border-good/30",
  warn: "bg-warnbg text-warnink border-warn/40",
  bad: "bg-badbg text-badink border-bad/30",
  neutral: "bg-sunk text-ink2 border-line",
  info: "bg-accent/10 text-accent border-accent/25",
};

export function toneOf(status: string): Tone {
  return MAP[status]?.tone ?? "neutral";
}

export function StatusBadge({ status, label, size = "sm" }: { status: string; label?: string; size?: "sm" | "xs" }) {
  const { t } = useTranslation();
  const m = MAP[status] ?? { tone: "neutral" as Tone, icon: Info };
  const Icon = m.icon;
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded border font-semibold ${TONE[m.tone]} ${size === "xs" ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-[11px]"}`}>
      <Icon aria-hidden className={size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {label ?? t(`status.${status}`, { defaultValue: status })}
    </span>
  );
}

export function Dot({ status }: { status: string }) {
  const tone = toneOf(status);
  const c = { good: "bg-good", warn: "bg-warn", bad: "bg-bad", neutral: "bg-line2", info: "bg-accent" }[tone];
  return <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-full ${c}`} />;
}

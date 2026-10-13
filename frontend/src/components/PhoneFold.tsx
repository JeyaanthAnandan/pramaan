import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Collapse } from "@/lib/motion";

const PHONE = "(max-width: 639px)";

/** True on a phone-width screen (follows rotation and window resizing). */
export function useIsPhone(): boolean {
  const [on, setOn] = useState(() => typeof window !== "undefined" && window.matchMedia(PHONE).matches);
  useEffect(() => {
    const q = window.matchMedia(PHONE);
    const f = () => setOn(q.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, []);
  return on;
}

/** On a phone, a long section starts folded behind a one-line summary; elsewhere it is shown as is. */
export function PhoneFold({ title, hint, children, className = "" }: { title: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  const phone = useIsPhone();
  const [open, setOpen] = useState(false);
  if (!phone) return <>{children}</>;
  return (
    <div className={className}>
      <button type="button" className="card flex w-full items-center gap-3 px-4 py-3 text-left transition hover:border-line2" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{title}</span>
          {hint && <span className="mt-0.5 block text-[12px] text-muted">{hint}</span>}
        </span>
        <ChevronDown className={`h-5 w-5 shrink-0 text-muted transition-transform duration-300 ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      <Collapse open={open}>
        <div className="pt-3">{children}</div>
      </Collapse>
    </div>
  );
}

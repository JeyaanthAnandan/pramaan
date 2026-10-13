import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { Languages, Menu, Moon, Sun, SunMoon, X } from "lucide-react";
import { LANGS, setLanguage } from "@/i18n";
import { lastProject } from "@/lib/session";
import { EASE, SPRING } from "@/lib/motion";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg viewBox="0 0 64 64" className="h-8 w-8" aria-hidden>
        <rect width="64" height="64" rx="14" fill="#14213d" />
        <circle cx="32" cy="32" r="17" fill="none" stroke="#f4efe2" strokeWidth="3" />
        <circle cx="32" cy="32" r="11" fill="none" stroke="#f4efe2" strokeWidth="1.5" strokeDasharray="2 3" />
        <path d="M25 32.5l5 5 9.5-11" fill="none" stroke="#7dd3a8" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-display text-[19px] font-semibold">Pramaan</span>
    </span>
  );
}

type Theme = "system" | "light" | "dark";
function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}
function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem("pramaan.theme") as Theme) || "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem("pramaan.theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  const cycle = () => {
    const next: Theme = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
    const go = () => {
      applyTheme(next);
      setTheme(next);
    };
    // cross-fade the whole page between themes where the browser supports view transitions
    const d = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    if (d.startViewTransition && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) d.startViewTransition(go);
    else go();
  };
  return [theme, cycle];
}

export function LangSwitch({ className = "" }: { className?: string }) {
  const { i18n, t } = useTranslation();
  return (
    <label className={`relative inline-flex items-center ${className}`}>
      <span className="sr-only">{t("nav.language")}</span>
      <Languages className="pointer-events-none absolute left-2.5 h-4 w-4 text-muted" aria-hidden />
      <select
        value={i18n.language}
        onChange={(e) => void setLanguage(e.target.value)}
        className="min-h-[40px] appearance-none rounded-xl border border-line bg-surface pl-8 pr-3 text-sm font-medium text-ink hover:bg-sunk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        {LANGS.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** The header gains a shadow once the page scrolls under it. */
function useScrolled(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const f = () => setOn(window.scrollY > 8);
    f();
    window.addEventListener("scroll", f, { passive: true });
    return () => window.removeEventListener("scroll", f);
  }, []);
  return on;
}

export function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [theme, cycle] = useTheme();
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  const scrolled = useScrolled();
  useEffect(() => {
    setMenu(false);
  }, [loc.pathname]);
  const links = [
    { to: lastProject() ? `/p/${lastProject()}/capture` : "/start", label: t("nav.workspace") },
    { to: "/proof", label: t("nav.proof") },
    { to: "/copilot", label: t("nav.copilot") },
    { to: "/metrics", label: t("nav.metrics") },
    { to: "/architecture", label: t("nav.architecture") },
  ];
  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : SunMoon;
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        {t("nav.skip")}
      </a>
      <header className={`sticky top-0 z-30 border-b border-t-[3px] border-t-rule bg-page/85 backdrop-blur-md transition-shadow duration-300 ${scrolled ? "border-b-line shadow-[0_6px_20px_-14px_rgb(20_27_43/0.35)]" : "border-b-line/80"}`}>
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" aria-label="Pramaan home">
            <Logo />
          </Link>
          <nav className="ml-6 hidden items-center gap-1 lg:flex" aria-label="Main">
            {links.map((l) => {
              const on = l.to.startsWith("/p/") || l.to === "/start" ? loc.pathname.startsWith("/p/") : loc.pathname === l.to;
              return (
                <NavLink key={l.to} to={l.to} className={`relative rounded-lg px-3 py-2 text-sm font-medium transition-colors ${on ? "text-ink" : "text-ink2 hover:text-ink"}`}>
                  {on && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-lg bg-sunk" transition={SPRING} aria-hidden />}
                  <span className="relative">{l.label}</span>
                </NavLink>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LangSwitch className="hidden sm:inline-flex" />
            <button className="btn-quiet h-10 w-10 !px-0" onClick={cycle} aria-label={`${t("nav.theme")}: ${theme}`} title={`${t("nav.theme")}: ${theme}`}>
              <ThemeIcon className="h-[18px] w-[18px]" />
            </button>
            <button className="btn-quiet h-10 w-10 !px-0 lg:hidden" onClick={() => setMenu((m) => !m)} aria-label="Menu" aria-expanded={menu}>
              {menu ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
        <AnimatePresence initial={false}>
          {menu && (
            <motion.nav
              key="mobile"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="overflow-hidden border-t border-line bg-page lg:hidden"
              aria-label="Mobile"
            >
              <div className="px-4 pb-4 pt-2">
                {links.map((l) => (
                  <NavLink key={l.to} to={l.to} className="flex min-h-[44px] items-center rounded-lg px-3 text-sm font-medium text-ink hover:bg-sunk">
                    {l.label}
                  </NavLink>
                ))}
                <LangSwitch className="mt-2 w-full sm:hidden" />
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>
      {/* at least a screen tall: while a page loads, the footer stays below the fold instead of showing and then being pushed away */}
      <main id="main" className="min-h-[calc(100svh-4rem)]">{children}</main>
      <footer className="mt-16 border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-8 text-[12px] text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span>
            <b className="text-ink2">Pramaan</b> — {t("app.tagline")} {t("app.disclaimer")}
          </span>
          <span>Google Cloud AI Builder Cup 2026 · Innovative Warriors · Gemini · ADK · Cloud Run</span>
        </div>
      </footer>
    </div>
  );
}

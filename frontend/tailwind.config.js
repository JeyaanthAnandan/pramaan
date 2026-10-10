/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        page: v("page"),
        surface: v("surface"),
        sunk: v("sunk"),
        ink: v("ink"),
        ink2: v("ink2"),
        muted: v("muted"),
        line: v("line"),
        line2: v("line2"),
        accent: v("accent"),
        accentink: v("accentink"),
        good: v("good"),
        goodink: v("goodink"),
        goodbg: v("goodbg"),
        warn: v("warn"),
        warnink: v("warnink"),
        warnbg: v("warnbg"),
        bad: v("bad"),
        badink: v("badink"),
        badbg: v("badbg"),
        s1: v("s1"),
        s2: v("s2"),
        s3: v("s3"),
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "-apple-system", '"Segoe UI"', '"Noto Sans Devanagari"', '"Noto Sans Tamil"', "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgb(var(--line) / 0.6), 0 1px 2px rgb(0 0 0 / 0.04)",
        lift: "0 12px 32px -12px rgb(0 0 0 / 0.18), 0 2px 6px rgb(0 0 0 / 0.06)",
      },
      keyframes: {
        pulsebox: { "0%,100%": { boxShadow: "0 0 0 0 rgb(var(--accent) / 0.55)" }, "50%": { boxShadow: "0 0 0 6px rgb(var(--accent) / 0)" } },
        rise: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        sheet: { from: { transform: "translateX(24px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        draw: { from: { strokeDashoffset: "1" }, to: { strokeDashoffset: "0" } },
      },
      animation: {
        pulsebox: "pulsebox 1.6s ease-in-out infinite",
        rise: "rise .35s ease-out both",
        sheet: "sheet .25s ease-out both",
      },
    },
  },
  plugins: [],
};

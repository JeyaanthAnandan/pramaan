import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en";

// English ships with the app; Hindi, Tamil and Vietnamese load when someone picks them (each is a
// separate chunk), so the first load stays small for everyone.
const LOADERS: Record<string, () => Promise<{ default: Record<string, unknown> }>> = {
  hi: () => import("./hi"),
  ta: () => import("./ta"),
  vi: () => import("./vi"),
};

export async function loadLanguage(lng: string): Promise<void> {
  if (lng === "en" || i18n.hasResourceBundle(lng, "translation") || !LOADERS[lng]) return;
  const m = await LOADERS[lng]();
  i18n.addResourceBundle(lng, "translation", m.default, true, true);
}

/** Switch the UI language, loading it first if needed. */
export async function setLanguage(lng: string): Promise<void> {
  await loadLanguage(lng);
  await i18n.changeLanguage(lng);
}

export const LANGS = [
  { code: "en", label: "English", short: "EN" },
  { code: "hi", label: "हिंदी", short: "हि" },
  { code: "ta", label: "தமிழ்", short: "த" },
  { code: "vi", label: "Tiếng Việt", short: "VI" },
] as const;

function initial(): string {
  try {
    const saved = localStorage.getItem("pramaan.lang");
    if (saved && LANGS.some((l) => l.code === saved)) return saved;
  } catch {
    /* storage may be unavailable */
  }
  return "en";
}

export const ready: Promise<void> = (async () => {
  await i18n.use(initReactI18next).init({
    resources: { en: { translation: en } },
    lng: "en",
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  const start = initial();
  if (start !== "en") await setLanguage(start).catch(() => undefined); // offline: stay in English
  document.documentElement.lang = i18n.language || "en";
})();

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem("pramaan.lang", lng);
  } catch {
    /* ignore */
  }
});
export default i18n;

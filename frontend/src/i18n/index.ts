import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en";
import hi from "./hi";
import ta from "./ta";
import vi from "./vi";

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

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, ta: { translation: ta }, vi: { translation: vi } },
  lng: initial(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem("pramaan.lang", lng);
  } catch {
    /* ignore */
  }
});
document.documentElement.lang = i18n.language;

export default i18n;

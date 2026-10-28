import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import enGB from "./locales/en-GB.json";
import deCH from "./locales/de-CH.json";
import frCH from "./locales/fr-CH.json";

export const LANGUAGES = [
  { code: "en-GB", short: "en", label: "English" },
  { code: "de-CH", short: "de", label: "Deutsch" },
  { code: "fr-CH", short: "fr", label: "Français" },
] as const;

function initialLanguage(): string {
  try {
    const saved = localStorage.getItem("sst.lang");
    if (saved && LANGUAGES.some((l) => l.code === saved)) return saved;
  } catch {
    /* storage unavailable */
  }
  const nav = (navigator.language || "en").toLowerCase();
  if (nav.startsWith("de")) return "de-CH";
  if (nav.startsWith("fr")) return "fr-CH";
  return "en-GB";
}

void i18n.use(initReactI18next).init({
  resources: {
    "en-GB": { translation: enGB },
    "de-CH": { translation: deCH },
    "fr-CH": { translation: frCH },
  },
  lng: initialLanguage(),
  fallbackLng: "en-GB",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem("sst.lang", lng);
  } catch {
    /* ignore */
  }
});
document.documentElement.lang = i18n.language;

/** Two-letter code the API stores: en, de or fr. */
export const shortLocale = (lng: string = i18n.language): "en" | "de" | "fr" =>
  lng.startsWith("de") ? "de" : lng.startsWith("fr") ? "fr" : "en";

/** Swiss currency formatting: CHF 24.00, CHF 1’234.50 */
export function formatChf(cents: number | null | undefined, currency = "CHF"): string {
  if (cents === null || cents === undefined) return "–";
  return new Intl.NumberFormat(i18n.language, {
    style: "currency",
    currency,
    currencyDisplay: "code",
  }).format(cents / 100);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(iso));
}

export default i18n;

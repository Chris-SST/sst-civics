import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import enGB from "./locales/en-GB.json";
import deCH from "./locales/de-CH.json";
import frCH from "./locales/fr-CH.json";
import itCH from "./locales/it-CH.json";
import ptPT from "./locales/pt-PT.json";
import esES from "./locales/es-ES.json";
import sqAL from "./locales/sq-AL.json";
import trTR from "./locales/tr-TR.json";

export const LANGUAGES = [
  { code: "en-GB", short: "en", label: "English" },
  { code: "de-CH", short: "de", label: "Deutsch" },
  { code: "fr-CH", short: "fr", label: "Français" },
  { code: "it-CH", short: "it", label: "Italiano" },
  { code: "pt-PT", short: "pt", label: "Português" },
  { code: "es-ES", short: "es", label: "Español" },
  { code: "sq-AL", short: "sq", label: "Shqip" },
  { code: "tr-TR", short: "tr", label: "Türkçe" },
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
  if (nav.startsWith("it")) return "it-CH";
  if (nav.startsWith("pt")) return "pt-PT";
  if (nav.startsWith("es")) return "es-ES";
  if (nav.startsWith("sq")) return "sq-AL";
  if (nav.startsWith("tr")) return "tr-TR";
  return "en-GB";
}

void i18n.use(initReactI18next).init({
  resources: {
    "en-GB": { translation: enGB },
    "de-CH": { translation: deCH },
    "fr-CH": { translation: frCH },
    "it-CH": { translation: itCH },
    "pt-PT": { translation: ptPT },
    "es-ES": { translation: esES },
    "sq-AL": { translation: sqAL },
    "tr-TR": { translation: trTR },
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

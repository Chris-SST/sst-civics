/** Links from the app to pages of the public guide site (imprint, contact, terms, privacy, FAQ).
 * The guide site is the app's host without "app." (app.viapunt.ch -> viapunt.ch); in local
 * development it is the staging guide. Legal and contact pages exist in German and English only;
 * the FAQ exists in every language. Slugs must match site/src/i18n/pages.mjs. */

const SLUGS = {
  imprint: { de: "impressum", en: "imprint" },
  contact: { de: "kontakt", en: "contact" },
  terms: { de: "nutzungsbedingungen", en: "terms" },
  privacy: { de: "datenschutz", en: "privacy" },
  about: { de: "ueber-viapunt", en: "about" },
} as const;

export type GuidePage = keyof typeof SLUGS | "faq";

export function guideBase(): string {
  const { protocol, hostname } = window.location;
  if (hostname.startsWith("app.")) return `${protocol}//${hostname.slice(4)}`;
  return "https://staging.viapunt.ch";
}

/** `lang` is a short code such as "de" or "fr". */
export function guideUrl(page: GuidePage, lang: string): string {
  if (page === "faq") return `${guideBase()}/${lang}/faq/`;
  const l = lang === "de" ? "de" : "en";
  return `${guideBase()}/${l}/${SLUGS[page][l]}/`;
}

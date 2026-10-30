// Language and URL logic shared by astro.config.mjs (sitemap) and the pages.
// Plain JavaScript on purpose: the config file imports it before Astro starts.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const LOCALES = ["de", "en", "fr", "it", "pt", "es", "sq", "tr"];
export const DEFAULT_LOCALE = "de";
/** Languages that have full page copy of their own. The rest fall back to English chrome. */
export const COPY_LOCALES = ["de", "en"];

export const LOCALE_NAMES = {
  de: "Deutsch",
  en: "English",
  fr: "Français",
  it: "Italiano",
  pt: "Português",
  es: "Español",
  sq: "Shqip",
  tr: "Türkçe",
};

/**
 * Page keys with their slug per language. A language not listed uses `other`.
 * A guide file whose slug is not in this table keeps the same slug in every language.
 * The overview slug is `ueberblick` in German and `overview` elsewhere, as agreed.
 */
export const SLUGS = {
  overview: { de: "ueberblick", fr: "apercu", it: "panoramica", pt: "visao-geral", es: "resumen", sq: "pergjithesim", tr: "genel-bakis", other: "overview" },
  zurich: { de: "zuerich-schritt-fuer-schritt", other: "zurich-step-by-step" },
  documents: { de: "unterlagen", other: "documents" },
  test: { de: "grundkenntnistest", fr: "test-de-connaissances", it: "test-di-conoscenze", pt: "teste-de-conhecimentos", es: "prueba-de-conocimientos", sq: "testi-i-njohurive", tr: "bilgi-testi", other: "knowledge-test" },
  language: { de: "sprachzertifikate", other: "language-certificates" },
  fees: { de: "gebuehren", other: "fees" },
  calculator: { de: "rechner", fr: "calculateur", it: "calcolatore", pt: "calculadora", es: "calculadora", sq: "llogaritesi", tr: "hesaplayici", other: "calculator" },
  free: { de: "kostenlos", fr: "pratique-gratuite", it: "pratica-gratuita", pt: "pratica-gratuita", es: "practica-gratuita", sq: "praktike-falas", tr: "ucretsiz-pratik", other: "free-practice" },
  faq: { de: "faq", other: "faq" },
};

/** Pages built from templates, present in every language (copy falls back to English). */
export const STATIC_KEYS = ["calculator", "faq", "free"];

/** Card order on the home page. */
export const HOME_KEYS = ["overview", "zurich", "documents", "test", "language", "fees", "calculator", "free", "faq"];

export function slugFor(key, lang) {
  const row = SLUGS[key];
  if (!row) return key;
  return row[lang] ?? row.other;
}

/** Reverse lookup: the page key for a slug in a language (unknown slugs are their own key). */
export function keyFor(lang, slug) {
  for (const [key, row] of Object.entries(SLUGS)) {
    if ((row[lang] ?? row.other) === slug) return key;
  }
  return slug;
}

/** "/de/" for German home, "/en/overview/" for a page. Every language has a prefix; "/" only redirects to /de/. */
export function pathFor(lang, key) {
  const prefix = `/${lang}/`;
  return key === "home" ? prefix : `${prefix}${slugFor(key, lang)}/`;
}

/** Split a URL path into { lang, key } or null (404 and unknown shapes). */
export function parsePath(pathname) {
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length || !LOCALES.includes(parts[0])) return null;
  const lang = parts.shift();
  if (parts.length === 0) return { lang, key: "home" };
  if (parts.length === 1) return { lang, key: keyFor(lang, parts[0]) };
  return null;
}

/**
 * Read the guide content folder and list { lang, slug } of pages that are not drafts.
 * Folder and file names are the contract: guide/<lang>/<slug>.md.
 */
export function scanGuide(root) {
  const out = [];
  if (!existsSync(root)) return out;
  for (const lang of readdirSync(root)) {
    if (!LOCALES.includes(lang)) continue;
    for (const file of readdirSync(join(root, lang))) {
      if (!file.endsWith(".md")) continue;
      const text = readFileSync(join(root, lang, file), "utf8");
      if (/^draft:\s*true\s*$/m.test(text)) continue;
      out.push({ lang, slug: file.replace(/\.md$/, "") });
    }
  }
  return out;
}

/** Map of page key to the set of languages it exists in, including template pages and home. */
export function buildIndex(guidePages) {
  /** @type {Map<string, Set<string>>} */
  const index = new Map();
  const add = (key, lang) => {
    if (!index.has(key)) index.set(key, new Set());
    index.get(key).add(lang);
  };
  for (const lang of LOCALES) {
    add("home", lang);
    for (const key of STATIC_KEYS) add(key, lang);
  }
  for (const { lang, slug } of guidePages) add(keyFor(lang, slug), lang);
  return index;
}

/** [{ lang, path }] for every language the page exists in, in locale order. */
export function alternatesFor(index, key) {
  const langs = index.get(key);
  if (!langs) return [];
  return LOCALES.filter((l) => langs.has(l)).map((lang) => ({ lang, path: pathFor(lang, key) }));
}

/**
 * Where a link to page `key` should go for a reader in `lang`: their own language if the page
 * exists there, else English, else German, else null (the page does not exist yet).
 */
export function resolveHref(index, key, lang) {
  const langs = index.get(key);
  if (!langs) return null;
  for (const l of [lang, "en", "de"]) if (langs.has(l)) return pathFor(l, key);
  return null;
}

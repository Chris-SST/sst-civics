// Language and URL logic shared by astro.config.mjs (sitemap) and the pages.
// Plain JavaScript on purpose: the config file imports it before Astro starts.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

export const LOCALES = ["de", "en", "fr", "it", "pt", "es", "sq", "tr"];
export const DEFAULT_LOCALE = "en"; // the bare host and x-default go to English (3 Nov 2026)
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
  zurich: { de: "zuerich-schritt-fuer-schritt", fr: "zurich-etape-par-etape", it: "zurigo-passo-per-passo", pt: "zurique-passo-a-passo", es: "zurich-paso-a-paso", sq: "cyrihu-hap-pas-hapi", tr: "adim-adim-zurih", other: "zurich-step-by-step" },
  documents: { de: "unterlagen", it: "documenti", pt: "documentos", es: "documentos", sq: "dokumentet", tr: "belgeler", other: "documents" },
  test: { de: "grundkenntnistest", fr: "test-de-connaissances", it: "test-di-conoscenze", pt: "teste-de-conhecimentos", es: "prueba-de-conocimientos", sq: "testi-i-njohurive", tr: "bilgi-testi", other: "knowledge-test" },
  language: { de: "sprachzertifikate", fr: "certificats-de-langue", it: "certificati-linguistici", pt: "certificados-de-lingua", es: "certificados-de-idioma", sq: "certifikatat-e-gjuhes", tr: "dil-sertifikalari", other: "language-certificates" },
  fees: { de: "gebuehren", fr: "emoluments", it: "tasse", pt: "taxas", es: "tasas", sq: "tarifat", tr: "ucretler", other: "fees" },
  interview: { de: "einbuergerungsgespraech", fr: "entretien-de-naturalisation", it: "colloquio-di-naturalizzazione", pt: "entrevista-de-naturalizacao", es: "entrevista-de-naturalizacion", sq: "interviste-per-natyralizim", tr: "vatandaslik-mulakati", other: "naturalisation-interview" },
  // One page per area of the Zurich question catalogue, linked from the knowledge-test page.
  topicDemocracy: { de: "grundkenntnistest-demokratie", fr: "test-democratie-federalisme", it: "test-democrazia-federalismo", pt: "teste-democracia-federalismo", es: "prueba-democracia-federalismo", sq: "testi-demokracia-federalizmi", tr: "bilgi-testi-demokrasi", other: "knowledge-test-democracy" },
  topicSocial: { de: "grundkenntnistest-sozialstaat", fr: "test-etat-social", it: "test-stato-sociale", pt: "teste-estado-social", es: "prueba-estado-social", sq: "testi-shteti-social", tr: "bilgi-testi-sosyal-devlet", other: "knowledge-test-welfare-state" },
  topicHistory: { de: "grundkenntnistest-geschichte", fr: "test-histoire", it: "test-storia", pt: "teste-historia", es: "prueba-historia", sq: "testi-historia", tr: "bilgi-testi-tarih", other: "knowledge-test-history" },
  topicGeography: { de: "grundkenntnistest-geografie", fr: "test-geographie", it: "test-geografia", pt: "teste-geografia", es: "prueba-geografia", sq: "testi-gjeografia", tr: "bilgi-testi-cografya", other: "knowledge-test-geography" },
  topicCulture: { de: "grundkenntnistest-kultur", fr: "test-culture", it: "test-cultura", pt: "teste-cultura", es: "prueba-cultura", sq: "testi-kultura", tr: "bilgi-testi-kultur", other: "knowledge-test-culture" },
  topicZurich: { de: "grundkenntnistest-kanton-gemeinde", fr: "test-canton-commune", it: "test-cantone-comune", pt: "teste-cantao-municipio", es: "prueba-canton-municipio", sq: "testi-kantoni-komuna", tr: "bilgi-testi-kanton-komun", other: "knowledge-test-canton-commune" },
  calculator: { de: "rechner", fr: "calculateur", it: "calcolatore", pt: "calculadora", es: "calculadora", sq: "llogaritesi", tr: "hesaplayici", other: "calculator" },
  free: { de: "kostenlos", fr: "pratique-gratuite", it: "pratica-gratuita", pt: "pratica-gratuita", es: "practica-gratuita", sq: "praktike-falas", tr: "ucretsiz-pratik", other: "free-practice" },
  faq: { de: "faq", other: "faq" },
  // Tool pages and article indexes (template pages, present in every language).
  glossary: { de: "glossar", fr: "glossaire", it: "glossario", pt: "glossario", es: "glosario", sq: "fjalori", tr: "sozluk", other: "glossary" },
  eligibility: { de: "einbuergerung-check", fr: "verifier-eligibilite", it: "verifica-requisiti", pt: "verificar-requisitos", es: "comprobar-requisitos", sq: "kontrolli-i-kushteve", tr: "uygunluk-kontrolu", other: "eligibility-check" },
  checklist: { de: "zuerich-checkliste", fr: "zurich-liste-de-controle", it: "zurigo-lista-di-controllo", pt: "zurique-lista-de-verificacao", es: "zurich-lista-de-comprobacion", sq: "cyrihu-lista-e-kontrollit", tr: "zurih-kontrol-listesi", other: "zurich-checklist" },
  articles: { de: "ratgeber", it: "articoli", pt: "artigos", es: "articulos", sq: "artikuj", tr: "makaleler", other: "articles" },
  cantons: { de: "kantone", it: "cantoni", pt: "cantoes", es: "cantones", sq: "kantonet", tr: "kantonlar", other: "cantons" },
  // Politics in your canton (docs/politics-contract.md): overview page; per-canton index is <segment>/<canton>/.
  politics: { de: "politik", fr: "politique", it: "politica", pt: "politica", es: "politica", sq: "politika", tr: "siyaset", other: "politics" },
  imprint: { de: "impressum", other: "imprint" },
  contact: { de: "kontakt", other: "contact" },
  about: { de: "ueber-viapunt", other: "about" },
  terms: { de: "nutzungsbedingungen", other: "terms" },
  privacy: { de: "datenschutz", other: "privacy" },
};

/** Pages built from templates, present in every language (copy falls back to English). */
export const STATIC_KEYS = ["calculator", "faq", "free", "glossary", "eligibility", "checklist", "articles", "cantons", "politics"];

/** Every home-page card, in the order the help pack lists the pages (scripts/build_help_pack.py reads it). */
export const HOME_KEYS = ["overview", "zurich", "documents", "test", "interview", "language", "fees", "calculator", "free", "faq", "glossary", "eligibility", "checklist"];

/** The home-page card groups: pages for everyone in Switzerland, then one group per canton with pages of its own. */
export const HOME_GROUPS = [
  { id: "swiss", keys: ["overview", "language", "calculator", "eligibility", "glossary", "free", "faq"] },
  { id: "zh", keys: ["zurich", "documents", "checklist", "test", "interview", "fees"] },
];

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

/** "/de/" for German home, "/en/overview/" for a page. Every language has a prefix; "/" only redirects to /en/. */
export function pathFor(lang, key) {
  const prefix = `/${lang}/`;
  return key === "home" ? prefix : `${prefix}${slugFor(key, lang)}/`;
}

/**
 * Article and canton-guide URL segments per language (docs/articles-contract.md section 2).
 * Index keys of articles are "article:<key>" (kind article and canton share one key space).
 */
export const ARTICLE_SEGMENTS = {
  article: { en: "articles", de: "ratgeber", fr: "articles", it: "articoli", pt: "artigos", es: "articulos", sq: "artikuj", tr: "makaleler" },
  canton: { en: "cantons", de: "kantone", fr: "cantons", it: "cantoni", pt: "cantoes", es: "cantones", sq: "kantonet", tr: "kantonlar" },
};
// The politics kinds (docs/politics-contract.md) share one URL segment: /<lang>/<segment>/<canton>/<slug>/.
export const POLITICS_KINDS = ["roundup", "vote", "whoswho"];
for (const kind of POLITICS_KINDS) {
  ARTICLE_SEGMENTS[kind] = { en: "politics", de: "politik", fr: "politique", it: "politica", pt: "politica", es: "politica", sq: "politika", tr: "siyaset" };
}
export const isPoliticsKind = (kind) => POLITICS_KINDS.includes(kind);

/** "/de/ratgeber/mein-slug/" for an article or canton guide; "/de/politik/zh/mein-slug/" for a politics page (needs `canton`). */
export function articlePath(lang, kind, slug, canton) {
  if (isPoliticsKind(kind)) return `/${lang}/${ARTICLE_SEGMENTS[kind][lang]}/${canton}/${slug}/`;
  return `/${lang}/${ARTICLE_SEGMENTS[kind][lang]}/${slug}/`;
}

/** "/en/politics/zh/": the politics index of one canton. */
export function politicsPath(lang, canton) {
  return `${pathFor(lang, "politics")}${canton}/`;
}

/** Split a URL path into { lang, key } or null (404 and unknown shapes). `index` lets article URLs resolve. */
export function parsePath(pathname, index) {
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length || !LOCALES.includes(parts[0])) return null;
  const lang = parts.shift();
  if (parts.length === 0) return { lang, key: "home" };
  if (parts.length === 1) return { lang, key: keyFor(lang, parts[0]) };
  if (parts.length === 2 && parts[0] === slugFor("politics", lang) && index?.has(`politics:${parts[1]}`)) {
    return { lang, key: `politics:${parts[1]}` };
  }
  if (parts.length >= 2 && index?.articleByPath) {
    const key = index.articleByPath.get(`/${lang}/${parts.join("/")}/`);
    if (key) return { lang, key: `article:${key}` };
  }
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

/** The value of a top-level scalar in a YAML front matter block, unquoted ("" if absent). */
function frontScalar(front, name) {
  const m = new RegExp(`^${name}:[ \t]*(.*?)[ \t]*$`, "m").exec(front);
  return m ? m[1].replace(/^["']|["']$/g, "") : "";
}

/**
 * List { lang, key, kind, slug } of the article files in `root` (<root>/<lang>/<slug>.md).
 * Reads only the front matter, with plain regexes (this runs in astro.config before Astro starts);
 * the content collection does the full validation.
 */
export function scanArticles(root) {
  const out = [];
  if (!existsSync(root)) return out;
  for (const lang of readdirSync(root)) {
    const dir = join(root, lang);
    if (!LOCALES.includes(lang) || !statSync(dir).isDirectory()) continue;
    for (const file of readdirSync(dir)) {
      if (!file.endsWith(".md")) continue;
      const text = readFileSync(join(dir, file), "utf8").replace(/^﻿/, "").replace(/\r\n/g, "\n");
      const m = /^---\n([\s\S]*?)\n---/.exec(text);
      if (!m) continue;
      const kind = frontScalar(m[1], "kind") || "article";
      const key = frontScalar(m[1], "key");
      if (!key || !ARTICLE_SEGMENTS[kind]) continue;
      out.push({ lang, key, kind, slug: frontScalar(m[1], "slug") || file.replace(/\.md$/, ""), canton: frontScalar(m[1], "canton") || undefined });
    }
  }
  return out;
}

/**
 * Map of page key to the set of languages it exists in, including template pages and home.
 * Articles are keyed "article:<key>"; `index.articles` maps "<lang>/<key>" to { kind, slug } and
 * `index.articleByPath` maps a URL path back to the key.
 */
export function buildIndex(guidePages, articles = []) {
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
  index.articles = new Map();
  index.articleByPath = new Map();
  for (const { lang, key, kind, slug, canton } of articles) {
    if (isPoliticsKind(kind) && !canton) continue; // the content collection reports the missing canton
    add(`article:${key}`, lang);
    index.articles.set(`${lang}/${key}`, { kind, slug, canton });
    index.articleByPath.set(articlePath(lang, kind, slug, canton), key);
    // A canton's politics index exists in every language (English fallback), once it has a page.
    if (isPoliticsKind(kind)) for (const l of LOCALES) add(`politics:${canton}`, l);
  }
  return index;
}

/** The URL path of page `key` in `lang` (guide pages, tools, home and "article:<key>" keys). */
export function pathOf(index, lang, key) {
  if (key.startsWith("article:")) {
    const a = index.articles?.get(`${lang}/${key.slice(8)}`);
    return a ? articlePath(lang, a.kind, a.slug, a.canton) : null;
  }
  if (key.startsWith("politics:")) return politicsPath(lang, key.slice(9));
  return pathFor(lang, key);
}

/** [{ lang, path }] for every language the page exists in, in locale order. */
export function alternatesFor(index, key) {
  const langs = index.get(key);
  if (!langs) return [];
  return LOCALES.filter((l) => langs.has(l)).map((lang) => ({ lang, path: pathOf(index, lang, key) }));
}

/**
 * Where a link to page `key` should go for a reader in `lang`: their own language if the page
 * exists there, else English, else German, else null (the page does not exist yet).
 */
export function resolveHref(index, key, lang) {
  const langs = index.get(key);
  if (!langs) return null;
  for (const l of [lang, "en", "de"]) if (langs.has(l)) return pathOf(index, l, key);
  return null;
}

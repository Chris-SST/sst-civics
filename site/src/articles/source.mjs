// Reads the article files (docs/articles-contract.md) and resolves their link placeholders.
// Plain JavaScript with no Astro imports, so the content config, the tests and the page code can
// share it. Anything that breaks the contract throws an Error whose message names the file; the
// build then fails loudly (a failed build leaves the live site unchanged).
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "yaml";
import { LOCALES, SLUGS, buildIndex, resolveHref, scanGuide, articlePath, ARTICLE_SEGMENTS } from "../i18n/pages.mjs";

export const CATEGORIES = ["eligibility", "cantons", "test", "process", "after"];

/** Directory of the article files: ARTICLES_DIR, else src/content/articles (git-ignored). */
export function articlesDir() {
  return resolve(process.env.ARTICLES_DIR || "./src/content/articles");
}

const here = (rel) => fileURLToPath(new URL(rel, import.meta.url));

/** Index of the guide and legal pages (and tool pages) that exist, for resolving `guide:` links. */
export function guideIndex() {
  return buildIndex([...scanGuide(here("../content/guide")), ...scanGuide(here("../content/legal"))]);
}

/** Every `<lang>/<slug>.md` under `root`: { lang, file, name, front, body }. Empty if the folder is missing. */
export function readArticleFiles(root) {
  const out = [];
  if (!existsSync(root)) return out;
  for (const lang of readdirSync(root).sort()) {
    const dir = join(root, lang);
    if (!statSync(dir).isDirectory()) continue;
    if (!LOCALES.includes(lang)) throw new Error(`${dir}: "${lang}" is not a language folder (${LOCALES.join(", ")})`);
    for (const name of readdirSync(dir).sort()) {
      if (!name.endsWith(".md") || name.startsWith(".")) continue; // .md.tmp files are in-flight writes
      const file = join(dir, name);
      const text = readFileSync(file, "utf8").replace(/^﻿/, "").replace(/\r\n/g, "\n");
      const m = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(text);
      if (!m) throw new Error(`${file}: no YAML front matter between --- lines`);
      let front;
      try {
        front = yaml.parse(m[1]);
      } catch (e) {
        throw new Error(`${file}: front matter is not valid YAML: ${e.message}`);
      }
      if (!front || typeof front !== "object") throw new Error(`${file}: front matter is empty`);
      out.push({ lang, file, name: basename(name, ".md"), front, body: m[2].trim() });
    }
  }
  return out;
}

const KEY_RE = /^[a-z0-9-]+$/;

/** Checks that need every file at once, and the per-file identity rules. Throws on the first problem. */
function checkIdentity(files) {
  const keyKind = new Map(); // key -> kind (one key space for articles and canton guides)
  const seen = new Set();
  const slugs = new Set();
  for (const { lang, file, name, front } of files) {
    const where = (msg) => new Error(`${file}: ${msg}`);
    if (typeof front.key !== "string" || !KEY_RE.test(front.key)) throw where(`key must match [a-z0-9-]+ (got ${JSON.stringify(front.key)})`);
    if (!ARTICLE_SEGMENTS[front.kind]) throw where(`kind must be "article" or "canton" (got ${JSON.stringify(front.kind)})`);
    if (front.lang !== lang) throw where(`lang is ${JSON.stringify(front.lang)} but the file is in the ${lang}/ folder`);
    if (front.slug !== name) throw where(`slug ${JSON.stringify(front.slug)} must equal the file name "${name}"`);
    if (keyKind.has(front.key) && keyKind.get(front.key) !== front.kind) {
      throw where(`key "${front.key}" is used for both an article and a canton guide`);
    }
    keyKind.set(front.key, front.kind);
    if (seen.has(`${lang}/${front.key}`)) throw where(`a second ${lang} file has the key "${front.key}"`);
    seen.add(`${lang}/${front.key}`);
    const url = articlePath(lang, front.kind, front.slug);
    if (slugs.has(url)) throw where(`another file already has the URL ${url}`);
    slugs.add(url);
    if (Array.isArray(front.related)) {
      for (const k of front.related) {
        if (!(k in SLUGS) && k !== "home") throw where(`related: "${k}" is not a guide page key (see SLUGS in src/i18n/pages.mjs)`);
      }
    }
  }
}

/** Body rules from the contract that the site enforces. */
function checkBody(file, body) {
  const fail = (msg) => {
    throw new Error(`${file}: ${msg}`);
  };
  if (!body) fail("the body is empty");
  // Skip fenced code when looking for forbidden things.
  const prose = body.replace(/^(```|~~~)[\s\S]*?^\1/gm, "");
  if (/^# /m.test(prose)) fail('the body has an H1 ("# "); the title is the H1, use ## for sections');
  if (/!\[[^\]]*\]\(/.test(prose)) fail("images are not allowed in the body");
  if (/<\/?[A-Za-z][A-Za-z0-9-]*(\s[^>\n]*)?>/.test(prose)) fail("raw HTML is not allowed in the body");
  if (/\]\(\s*http:\/\//i.test(prose)) fail("external links must be https:// links");
  if (/\]\(\s*\//.test(prose)) fail("use guide:<key>, article:<key> or try: for internal links, not a site path");
}

const PLACEHOLDER = /\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(guide|article|try):([^)\s]*)\s*\)/g;

/**
 * Replace the link placeholders in one article's body.
 *  - `[t](guide:<key>)`: key must be in SLUGS (or "home"); resolved to the reader's language, else
 *    English, else German. An unknown key, or a page that exists in no language, throws.
 *  - `[t](article:<key>)`: the same key in the file's language, else English; if neither is
 *    published the link is dropped and only the text stays.
 *  - `[t](try:)`: the free practice in the app. Anything after "try:" throws.
 */
export function resolvePlaceholders({ file, lang, body, pages, published, appUrl }) {
  const fail = (msg) => {
    throw new Error(`${file}: ${msg}`);
  };
  const out = body.replace(PLACEHOLDER, (_all, text, kind, rest) => {
    if (kind === "try") {
      if (rest !== "") fail(`"try:${rest}" is not valid; write [text](try:)`);
      return `[${text}](${appUrl}/try?lang=${lang})`;
    }
    if (kind === "guide") {
      const [key, frag] = rest.split("#");
      if (!key || (!(key in SLUGS) && key !== "home")) fail(`guide:${key || ""} is not a guide page key (see SLUGS in src/i18n/pages.mjs)`);
      const href = resolveHref(pages, key, lang);
      if (!href) fail(`guide:${key} does not exist in ${lang}, en or de`);
      return `[${text}](${href}${frag ? "#" + frag : ""})`;
    }
    if (!KEY_RE.test(rest)) fail(`article:${rest} is not a valid article key ([a-z0-9-]+)`);
    const hit = published.get(`${lang}/${rest}`) ?? published.get(`en/${rest}`);
    return hit ? `[${text}](${hit})` : text;
  });
  if (/\]\(\s*(guide|article|try):/.test(out)) fail("a guide:, article: or try: link could not be read; use [text](guide:key)");
  if (/^\s{0,3}\[[^\]]+\]:\s*(guide|article|try):/m.test(out)) fail("reference-style links with placeholders are not supported; use [text](guide:key)");
  return out;
}

/**
 * Everything the content collection needs: for each article file, the raw front matter and the body
 * with placeholders resolved. Throws on any contract violation.
 */
export function collectArticles({ root = articlesDir(), appUrl } = {}) {
  const files = readArticleFiles(root);
  checkIdentity(files);
  const pages = guideIndex();
  const published = new Map();
  for (const { lang, front } of files) published.set(`${lang}/${front.key}`, articlePath(lang, front.kind, front.slug));
  const base = (appUrl || process.env.APP_URL || "https://app.staging.viapunt.ch").replace(/\/+$/, "");
  return files.map(({ lang, file, front, body }) => {
    checkBody(file, body);
    const resolved = resolvePlaceholders({ file, lang, body, pages, published, appUrl: base });
    return { id: `${lang}/${front.slug}`, file, front, body: resolved, raw: body };
  });
}

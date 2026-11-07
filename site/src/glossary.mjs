// Reads the glossary YAML files (content/glossary/<lang>.yaml, one level above site/) at build
// time. The build therefore needs ../content/glossary to exist (GLOSSARY_DIR overrides the path);
// the server site builder copies it in next to site/. A missing folder fails the build, so a
// release never goes out with an empty glossary.
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import yaml from "yaml";

export function glossaryDir() {
  return resolve(process.env.GLOSSARY_DIR || "../content/glossary");
}

function load(dir, lang) {
  const file = join(dir, `${lang}.yaml`);
  if (!existsSync(file)) return null;
  const doc = yaml.parse(readFileSync(file, "utf8"));
  return Array.isArray(doc?.terms) ? doc.terms : [];
}

export function anchorFor(term) {
  return term
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Entries for one page language, sorted by the German term. English is the base: each entry has
 * the translation and note of `lang` where the file has them, else the English ones (`fallback`
 * is true when the explanation shown is English, e.g. for German, which has no file).
 */
export function glossaryFor(lang) {
  const dir = glossaryDir();
  const en = load(dir, "en");
  if (!en) throw new Error(`Glossary not found: ${join(dir, "en.yaml")}. The site build needs content/glossary (set GLOSSARY_DIR to move it).`);
  const own = lang === "en" ? null : load(dir, lang);
  const ownBy = new Map((own ?? []).map((t) => [t.term_de, t]));
  const entries = en.map((base) => {
    const mine = ownBy.get(base.term_de);
    const translation = mine?.translation || base.translation;
    const note = mine?.note || base.note || "";
    const fallback = lang !== "en" && (!mine?.translation || (!mine?.note && !!base.note));
    return {
      id: anchorFor(base.term_de),
      term: base.term_de,
      translation,
      note,
      keepGerman: Boolean(mine?.keep_german ?? base.keep_german),
      fallback: lang !== "en" && !mine?.translation,
      noteFallback: fallback,
    };
  });
  return entries.sort((a, b) => a.term.localeCompare(b.term, "de"));
}

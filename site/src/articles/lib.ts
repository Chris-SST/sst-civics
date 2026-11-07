// Helpers shared by the pages that list or link articles.
import { getCollection, type CollectionEntry } from "astro:content";
import { articlePath, isPoliticsKind, scanArticles } from "../i18n/pages.mjs";
import { articlesDir } from "./source.mjs";

export type ArticleEntry = CollectionEntry<"articles">;

/** All article and canton-guide files, newest first (ties by key, so the order is stable). */
export async function allArticles(): Promise<ArticleEntry[]> {
  // Asking Astro for an empty collection logs a warning per call, so skip it when there are no files.
  if (scanArticles(articlesDir()).length === 0) return [];
  const all = await getCollection("articles");
  return all.sort(
    (a, b) => b.data.published.getTime() - a.data.published.getTime() || a.data.key.localeCompare(b.data.key) || a.data.lang.localeCompare(b.data.lang),
  );
}

/** One entry per key for a reader in `lang`: their language where it exists, else English. */
export function forLang(all: ArticleEntry[], lang: string): ArticleEntry[] {
  const out: ArticleEntry[] = [];
  const seen = new Set<string>();
  for (const e of all) {
    if (seen.has(e.data.key)) continue;
    const mine = all.find((x) => x.data.key === e.data.key && x.data.lang === lang) ?? all.find((x) => x.data.key === e.data.key && x.data.lang === "en");
    if (!mine) continue;
    seen.add(e.data.key);
    out.push(mine);
  }
  return out.sort((a, b) => b.data.published.getTime() - a.data.published.getTime() || a.data.key.localeCompare(b.data.key));
}

export const hrefOf = (e: ArticleEntry) => articlePath(e.data.lang, e.data.kind, e.data.slug, e.data.canton);

export const isPolitics = (e: ArticleEntry) => isPoliticsKind(e.data.kind);
/** Articles and canton guides only (the home row and article indexes leave politics pages out). */
export const withoutPolitics = (list: ArticleEntry[]) => list.filter((e) => !isPolitics(e));

/** Politics pages of one canton for a reader in `lang` (English fallback), newest first. */
export function politicsFor(all: ArticleEntry[], lang: string, canton: string): ArticleEntry[] {
  return forLang(all.filter(isPolitics), lang).filter((e) => e.data.canton === canton);
}

/** Cantons that have at least one politics page, sorted by code. */
export function politicsCantons(all: ArticleEntry[]): string[] {
  return [...new Set(all.filter(isPolitics).map((e) => e.data.canton as string))].sort();
}

/** Weeks, in milliseconds. */
export const WEEKS_8 = 8 * 7 * 24 * 3600 * 1000;

/** The newest round-up of a canton for a reader in `lang`. */
export function latestRoundup(all: ArticleEntry[], lang: string, canton: string): ArticleEntry | undefined {
  return politicsFor(all, lang, canton)
    .filter((e) => e.data.kind === "roundup")
    .sort((a, b) => (b.data.period_end ?? b.data.published).getTime() - (a.data.period_end ?? a.data.published).getTime())[0];
}

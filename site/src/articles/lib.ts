// Helpers shared by the pages that list or link articles.
import { getCollection, type CollectionEntry } from "astro:content";
import { articlePath, scanArticles } from "../i18n/pages.mjs";
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

export const hrefOf = (e: ArticleEntry) => articlePath(e.data.lang, e.data.kind, e.data.slug);

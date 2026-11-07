export const CATEGORIES: string[];
export function articlesDir(): string;
export function collectArticles(opts?: { root?: string; appUrl?: string }): {
  id: string;
  file: string;
  front: Record<string, unknown>;
  body: string;
  raw: string;
}[];

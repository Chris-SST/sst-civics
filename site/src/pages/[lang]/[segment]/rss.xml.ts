// RSS 2.0 feed per language: /<lang>/<articles segment>/rss.xml. It lists the articles and canton
// guides that exist in that language, newest first (up to 50). An empty site gives a valid feed
// with no items.
import type { APIRoute } from "astro";
import { LOCALES, articlePath, pathFor } from "../../../i18n/pages.mjs";
import { more } from "../../../i18n/more";
import { allArticles } from "../../../articles/lib";

export function getStaticPaths() {
  return LOCALES.map((lang) => ({ params: { lang, segment: pathFor(lang, "articles").split("/")[2] } }));
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export const GET: APIRoute = async ({ params, site }) => {
  const lang = params.lang as string;
  const base = (site ?? new URL("https://viapunt.ch")).toString().replace(/\/$/, "");
  const items = (await allArticles()).filter((e) => e.data.lang === lang).slice(0, 50);
  const self = `${base}${pathFor(lang, "articles")}rss.xml`;
  const m = more(lang).articles;
  const newest = items.reduce((a, e) => Math.max(a, e.data.updated.getTime()), 0);
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n` +
    `<title>${esc(m.rss.replace(/ \(RSS\)$/, ""))}</title>\n` +
    `<link>${esc(base + pathFor(lang, "articles"))}</link>\n` +
    `<description>${esc(m.indexDescription)}</description>\n` +
    `<language>${lang}</language>\n` +
    (newest ? `<lastBuildDate>${new Date(newest).toUTCString()}</lastBuildDate>\n` : "") +
    `<atom:link href="${esc(self)}" rel="self" type="application/rss+xml" />\n` +
    items
      .map((e) => {
        const url = base + articlePath(lang, e.data.kind, e.data.slug);
        return (
          `<item>\n<title>${esc(e.data.title)}</title>\n<link>${esc(url)}</link>\n<guid isPermaLink="true">${esc(url)}</guid>\n` +
          `<pubDate>${e.data.published.toUTCString()}</pubDate>\n<description>${esc(e.data.description)}</description>\n</item>\n`
        );
      })
      .join("") +
    `</channel>\n</rss>\n`;
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8" } });
};

// @ts-check
import { defineConfig, envField } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { fileURLToPath } from "node:url";
import { LOCALES, DEFAULT_LOCALE, scanGuide, scanArticles, buildIndex, parsePath, alternatesFor, pathFor, POLITICS_KINDS } from "./src/i18n/pages.mjs";
import { articlesDir } from "./src/articles/source.mjs";

// Public host of the guide site. Staging default; set SITE_URL at build time for production
// (the brand domain, see docs/runbooks/deploy-guide-site.md).
const site = (process.env.SITE_URL || "https://staging.viapunt.ch").replace(/\/+$/, "");

// Which language versions exist, read from the content folder, so each sitemap entry can list
// its translations (slugs differ per language, so the sitemap integration's own i18n matching
// by path would miss them).
const articles = scanArticles(articlesDir());
const index = buildIndex(
  [
    ...scanGuide(fileURLToPath(new URL("./src/content/guide", import.meta.url))),
    ...scanGuide(fileURLToPath(new URL("./src/content/legal", import.meta.url))),
  ],
  articles,
);
// The article and canton indexes are noindex while empty, so they stay out of the sitemap too.
const emptyIndexes = new Set([
  ...(articles.some((a) => a.kind === "article") ? [] : LOCALES.map((l) => pathFor(l, "articles"))),
  ...(articles.some((a) => a.kind === "canton") ? [] : LOCALES.map((l) => pathFor(l, "cantons"))),
  ...(articles.some((a) => POLITICS_KINDS.includes(a.kind)) ? [] : LOCALES.map((l) => pathFor(l, "politics"))),
]);

export default defineConfig({
  site,
  trailingSlash: "always",
  build: { format: "directory", inlineStylesheets: "auto" },
  // Never inline the calculator script: the CSP only allows script-src 'self'.
  vite: { build: { assetsInlineLimit: 0 } },
  i18n: {
    locales: LOCALES,
    defaultLocale: DEFAULT_LOCALE,
    routing: { prefixDefaultLocale: true, redirectToDefaultLocale: false },
  },
  env: {
    schema: {
      // Where the "Try 30 free questions" card points. Same domain as the site, `app.` host.
      APP_URL: envField.string({
        context: "server",
        access: "public",
        default: "https://app.staging.viapunt.ch",
      }),
    },
  },
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith("/404/") && new URL(page).pathname !== "/" && !emptyIndexes.has(new URL(page).pathname),
      serialize(item) {
        const parsed = parsePath(new URL(item.url).pathname, index);
        if (!parsed) return item;
        const alts = alternatesFor(index, parsed.key);
        if (alts.length < 2) return item;
        const links = alts.map((a) => ({ lang: a.lang, url: site + a.path }));
        const xdef = alts.find((a) => a.lang === DEFAULT_LOCALE) || alts[0];
        links.push({ lang: "x-default", url: site + xdef.path });
        return { ...item, links };
      },
    }),
  ],
});

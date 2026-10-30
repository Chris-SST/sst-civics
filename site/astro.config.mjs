// @ts-check
import { defineConfig, envField } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { fileURLToPath } from "node:url";
import { LOCALES, DEFAULT_LOCALE, scanGuide, buildIndex, parsePath, alternatesFor } from "./src/i18n/pages.mjs";

// Public host of the guide site. Staging default; set SITE_URL at build time for production
// (the brand domain, see docs/runbooks/deploy-guide-site.md).
const site = (process.env.SITE_URL || "https://civics-staging.swisssciencetutors.ch").replace(/\/+$/, "");

// Which language versions exist, read from the content folder, so each sitemap entry can list
// its translations (slugs differ per language, so the sitemap integration's own i18n matching
// by path would miss them).
const index = buildIndex(scanGuide(fileURLToPath(new URL("./src/content/guide", import.meta.url))));

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
        default: "https://app.civics-staging.swisssciencetutors.ch",
      }),
    },
  },
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith("/404/") && new URL(page).pathname !== "/",
      serialize(item) {
        const parsed = parsePath(new URL(item.url).pathname);
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

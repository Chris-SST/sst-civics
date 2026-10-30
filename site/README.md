# Guide site

Static public guide for the citizenship-test trainer (D-042, D-043, D-056). Astro, plain `.astro`
components, no UI framework. The only client-side script is the residence calculator.

## Commands

```
cd site
npm ci
npx astro check     # types, content schema, templates; must report 0 errors
npm run build       # writes dist/
npm run dev         # local preview on http://localhost:4321
```

Build-time settings (environment variables):

| Variable | Default | Used for |
| --- | --- | --- |
| `SITE_URL` | `https://civics-staging.swisssciencetutors.ch` | canonical URLs, hreflang, sitemap, `robots.txt` |
| `PUBLIC_UMAMI_WEBSITE_ID` | unset (no analytics) | Umami website id; when set, the page loads the cookie-free tracker from `/stats/script.js` (docs/runbooks/analytics.md) |
| `APP_URL` | `https://app.civics-staging.swisssciencetutors.ch` | target of the "Try 30 free questions" card (`/signup?lang=<lang>`) |

## Target

Lighthouse 90 or more on all four scores, mobile profile, for the home page, one guide page and
the calculator, before launch. No external requests except the self-hosted fonts; no images.

## Layout

- `src/content.config.ts`: schemas for `guide` and `faq` (Astro 7 requires this path, not `src/content/config.ts`).
- `src/content/guide/<lang>/<slug>.md`: one Markdown file per page and language; `src/content/faq/<lang>/*.md`: one FAQ item each.
- `src/i18n/pages.mjs`: locales, slug per language for each page, hreflang and sitemap logic.
- `src/i18n/ui.ts`: copy for the template pages in German and English, and the independence notice in all eight languages.
- `src/pages/[...path].astro`: every route; `src/layouts/`, `src/components/`: layout and components.
- `public/fonts/`: self-hosted fonts and their licences (copied from `web/public/fonts`).

All URLs have a language prefix (`/de/...`); `/` only redirects to `/de/`.

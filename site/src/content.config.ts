// Content collections. Astro 7 reads this file from `src/content.config.ts` (the older
// `src/content/config.ts` location is rejected). The schema is the one agreed with the
// content writer; do not change a field without telling them.
import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";
import { collectArticles } from "./articles/source.mjs";
import { SLUGS } from "./i18n/pages.mjs";

const lang = z.enum(["de", "en", "fr", "it", "pt", "es", "sq", "tr"]);

// Pages live at src/content/guide/<lang>/<slug>.md and are served at /<lang>/<slug>/
// (German without prefix). The id is "<lang>/<slug>" so the same slug can exist in two languages.
const guide = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "./src/content/guide",
    generateId: ({ entry }) => entry.replace(/\.md$/, ""),
  }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    lang,
    slug: z.string(),
    lastChecked: z.coerce.date(),
    sources: z.array(z.object({ title: z.string(), url: z.url() })),
    updated: z.coerce.date(),
    draft: z.boolean().default(false),
    cta: z.enum(["free-questions", "mock", "pass"]).default("free-questions"),
  }),
});

// Legal and contact pages (imprint, contact, about, terms, privacy) at
// src/content/legal/<lang>/<slug>.md, in German and English. `notice` is shown above the text and
// `contentLang` marks a page whose text is in another language (German pages showing English).
const legal = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "./src/content/legal",
    generateId: ({ entry }) => entry.replace(/\.md$/, ""),
  }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    lang,
    slug: z.string(),
    updated: z.coerce.date(),
    notice: z.string().optional(),
    contentLang: lang.optional(),
  }),
});

// FAQ items live at src/content/faq/<lang>/<name>.md; the Markdown body is the answer.
const faq = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "./src/content/faq",
    generateId: ({ entry }) => entry.replace(/\.md$/, ""),
  }),
  schema: z.object({
    lang,
    question: z.string(),
    order: z.number(),
  }),
});

// Articles and canton guides, written by the content pipeline to ARTICLES_DIR (default
// src/content/articles, git-ignored) as <lang>/<slug>.md. The format is docs/articles-contract.md.
// A custom loader because the body links ([t](guide:key), [t](article:key), [t](try:)) are
// resolved against the whole set of files before the Markdown is rendered. A missing or empty
// folder is fine: the collection is then empty.
const articles = defineCollection({
  loader: {
    name: "viapunt-articles",
    load: async ({ store, parseData, renderMarkdown, generateDigest }) => {
      store.clear();
      for (const a of collectArticles()) {
        const data = await parseData({ id: a.id, data: a.front, filePath: a.file });
        const rendered = await renderMarkdown(a.body);
        // The digest covers the resolved body, so a changed link target re-renders the entry.
        store.set({ id: a.id, data, body: a.body, rendered, digest: generateDigest({ front: a.front, body: a.body }) });
      }
    },
  },
  schema: z
    .object({
      key: z.string().regex(/^[a-z0-9-]+$/),
      kind: z.enum(["article", "canton"]),
      lang,
      slug: z.string().regex(/^[a-z0-9-]+$/).max(80),
      title: z.string().min(1).max(90),
      description: z.string().min(70).max(160),
      category: z.enum(["eligibility", "cantons", "test", "process", "after"]), // keep in step with CATEGORIES in articles/source.mjs
      canton: z.string().regex(/^[a-z]{2}$/).optional(),
      published: z.coerce.date(),
      updated: z.coerce.date(),
      checked: z.coerce.date(),
      summary: z.array(z.string().min(1)).min(3).max(5),
      sources: z.array(z.object({ title: z.string().min(1), url: z.url() })).min(2).max(12),
      faq: z.array(z.object({ q: z.string().min(1), a: z.string().min(1) })).min(3).max(5),
      related: z.array(z.string().refine((k) => k in SLUGS || k === "home", "not a guide page key")).max(4).default([]),
      machine_translated: z.boolean().default(false),
    })
    .refine((d) => d.kind !== "canton" || !!d.canton, { message: "a canton guide needs the two-letter canton code", path: ["canton"] }),
});

export const collections = { guide, faq, legal, articles };

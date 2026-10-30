// Content collections. Astro 7 reads this file from `src/content.config.ts` (the older
// `src/content/config.ts` location is rejected). The schema is the one agreed with the
// content writer; do not change a field without telling them.
import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

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

export const collections = { guide, faq };

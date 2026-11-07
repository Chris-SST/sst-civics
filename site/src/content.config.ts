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
      kind: z.enum(["article", "canton", "roundup", "vote", "whoswho"]),
      lang,
      slug: z.string().regex(/^[a-z0-9-]+$/).max(80),
      title: z.string().min(1).max(90),
      description: z.string().min(70).max(160),
      category: z.enum(["eligibility", "cantons", "test", "process", "after", "politics"]), // keep in step with CATEGORIES in articles/source.mjs
      canton: z.string().regex(/^[a-z]{2}$/).optional(),
      published: z.coerce.date(),
      updated: z.coerce.date(),
      checked: z.coerce.date(),
      summary: z.array(z.string().min(1)).min(3).max(6),
      sources: z.array(z.object({ title: z.string().min(1), url: z.url() })).min(1).max(20),
      faq: z.array(z.object({ q: z.string().min(1), a: z.string().min(1) })).max(5).default([]),
      related: z.array(z.string().refine((k) => k in SLUGS || k === "home" || /^[a-z0-9-]+$/.test(k), "not a guide page or article key")).max(4).default([]),
      machine_translated: z.boolean().default(false),
      // Politics pages (docs/politics-contract.md)
      period_start: z.coerce.date().optional(),
      period_end: z.coerce.date().optional(),
      vote_date: z.coerce.date().optional(),
      vote_level: z.enum(["cantonal", "federal"]).optional(),
      result: z
        .object({
          yes_percent: z.number().min(0).max(100),
          turnout_percent: z.number().min(0).max(100),
          accepted: z.boolean(),
        })
        .optional(),
    })
    .superRefine((d, ctx) => {
      const bad = (path: string, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
      const politics = d.kind === "roundup" || d.kind === "vote" || d.kind === "whoswho";
      if (!politics) {
        // Articles and canton guides keep their original ranges.
        if (d.category === "politics") bad("category", "category politics is only for the kinds roundup, vote and whoswho");
        if (d.summary.length > 5) bad("summary", "an article summary has 3-5 items");
        if (d.sources.length < 2 || d.sources.length > 12) bad("sources", "an article has 2-12 sources");
        if (d.faq.length < 3) bad("faq", "an article has 3-5 questions");
        for (const f of ["period_start", "period_end", "vote_date", "vote_level", "result"] as const) {
          if (d[f] !== undefined) bad(f, `${f} is only for politics pages`);
        }
        if (d.kind === "canton" && !d.canton) bad("canton", "a canton guide needs the two-letter canton code");
        if (d.kind === "article" && d.related.some((k) => !(k in SLUGS) && k !== "home")) bad("related", "not a guide page key");
        return;
      }
      if (d.category !== "politics") bad("category", `a ${d.kind} page needs category: politics`);
      if (!d.canton) bad("canton", "a politics page needs the canton code (ch for a federal vote)");
      if (d.kind === "roundup") {
        if (!d.period_start || !d.period_end) bad("period_start", "a roundup needs period_start and period_end");
        else if (d.period_end < d.period_start) bad("period_end", "period_end is before period_start");
      } else if (d.period_start || d.period_end) bad("period_start", "period_start and period_end are only for a roundup");
      if (d.kind === "vote") {
        if (!d.vote_date) bad("vote_date", "a vote needs vote_date");
        if (!d.vote_level) bad("vote_level", "a vote needs vote_level (cantonal or federal)");
        if (d.vote_level === "federal" && d.canton !== "ch") bad("canton", "a federal vote has canton: ch");
        if (d.vote_level === "cantonal" && d.canton === "ch") bad("canton", "a cantonal vote needs the canton's own code, not ch");
      } else {
        for (const f of ["vote_date", "vote_level", "result"] as const) if (d[f] !== undefined) bad(f, `${f} is only for a vote`);
      }
    }),
});

export const collections = { guide, faq, legal, articles };

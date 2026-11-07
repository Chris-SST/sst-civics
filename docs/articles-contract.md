# Articles and canton guides: the shared contract

Decided 7 November 2026 (D-073). Chris approved the content plan (`docs/content-plan.md`) and asked for an automated
process on the server that writes, reviews and publishes articles. He gets each proposed article by email 24 hours
before publication and may suggest changes. If he says nothing, it is published.

There are three parts, each with its own owner. This file is the interface between them. Change it only together.

| Part | Lives in | What it does |
|---|---|---|
| Site | `site/` | Renders articles and canton guides from Markdown files, with index pages, RSS, structured data and the home-page row |
| Pipeline | `app/articles/`, `worker/`, `prompts/articles/`, `scripts/articles.py`, `alembic/` | Plans, writes, fact-checks, translates, reviews, emails Chris, writes the files and requests a site build |
| Builder | `infra/sitebuilder/`, `infra/docker-compose.yml` | Builds the Astro site on the server whenever articles change, checks it and swaps the live release |

The topic queue is `content/articles/plan.yaml` (in git), and the published files live on the server (not in git).

## 1. The files

- Directory: `ARTICLES_DIR`. On the server this is the volume `articles`, mounted read-write in the worker at `/srv/articles` and read-only in the builder. In a local checkout the site falls back to `site/src/content/articles/`, which is git-ignored except for its `README.md`. CI and tests use the fixture set in `site/test-fixtures/articles/`.
- Layout: `<ARTICLES_DIR>/<lang>/<slug>.md`, with `lang` one of `de en fr it pt es sq tr`.
- The pipeline writes a file atomically (to `<name>.md.tmp`, then rename). It writes all languages of one article before it requests a build.
- An article exists in a language only if its file is there. English always exists, and the other seven are written when they pass review.

### Frontmatter (YAML)

```yaml
key: spouse-facilitated          # stable id, the same in every language; [a-z0-9-]+
kind: article                    # article | canton
lang: en
slug: married-to-a-swiss-citizen # URL slug in this language; ASCII [a-z0-9-]+, max 80 chars
title: "Married to a Swiss citizen? Facilitated naturalisation explained"   # H1, max 90 chars
description: "..."               # meta description, 70-160 chars
category: eligibility            # eligibility | cantons | test | process | after
canton: ag                       # kind canton only: two-letter canton code, lower case
published: 2026-11-16            # first publication date (YYYY-MM-DD)
updated: 2026-11-16              # last content change
checked: 2026-11-14              # date the facts were last checked against the sources
summary:                         # "In brief" box, 3-5 short sentences
  - "..."
sources:                         # 2-12 official or authoritative pages that were actually read
  - title: "SEM: Facilitated naturalisation"
    url: "https://www.sem.admin.ch/..."
faq:                             # 3-5 items, plain-text answers (no Markdown)
  - q: "..."
    a: "..."
related: [overview, calculator]  # 0-4 guide page keys from SLUGS in site/src/i18n/pages.mjs
machine_translated: false        # true for every language except English
```

### Body (Markdown)

- No H1, because the title is the H1. Sections are `##`, subsections `###`. Lists and tables (GFM) are allowed, but raw HTML and images are not.
- Internal links use placeholders that the site resolves for the article's language, falling back to English:
  - `[text](guide:<key>)`: a guide page key from `SLUGS`, for example `guide:calculator`, `guide:test`.
  - `[text](article:<key>)`: another article or canton guide by its `key`. If that article isn't published, the site renders the text without a link.
  - `[text](try:)`: the free practice in the app (`APP_URL` + `/try`).
- External links are plain `https://` links.
- The site adds the "In brief" box, the sources box, the FAQ, related pages and the soft call to action. The body must not contain any of them.
- About 900-1,300 words for an article, and 1,200-1,800 for a canton guide.

## 2. URLs

| kind | en | de | fr | it | pt | es | sq | tr |
|---|---|---|---|---|---|---|---|---|
| article | articles | ratgeber | articles | articoli | artigos | articulos | artikuj | makaleler |
| canton | cantons | kantone | cantons | cantoni | cantoes | cantones | kantonet | kantonlar |

- Page: `/<lang>/<segment>/<slug>/`. Index: `/<lang>/<segment>/` (the article index lists categories; the canton index lists cantons).
- RSS: `/<lang>/articles/rss.xml`, using that language's segment for the path. It covers articles and canton guides together.
- hreflang links all languages of the same `key`, with x-default = English. The sitemap includes them.
- The live check after publishing uses `https://<site>/<lang>/<segment>/<slug>/`, which must answer 200.

## 3. Build requests (pipeline → builder)

- The pipeline writes `<ARTICLES_DIR>/.build-request`, a JSON file: `{"requested_at": ISO, "reason": "publish spouse-facilitated"}`.
- The builder polls every 30 s. When `.build-request` is newer than its last build, it builds, checks and swaps. It then writes `<ARTICLES_DIR>/.build-status.json`, which the pipeline reads:
  `{"ok": true|false, "started_at", "finished_at", "release": "<id>", "requested_at": <copied from the request>, "error": "<last 40 lines>"|null}`.
  Since the builder mounts the articles read-only, it writes the status file to `site-releases/build-status.json`, which is outside the served `current` directory. The worker mounts `../site-releases` read-only at `/srv/site-releases`, and compose sets `SITEBUILD_STATUS_FILE=/srv/site-releases/build-status.json`. The status also carries `"building": true` while a build runs, plus `reason` and `source_rev`.
- On the server, `ARTICLES_DIR` is the host directory `/opt/civics-prod/articles` (`/opt/civics/articles` on staging), bind-mounted, owned by uid 10001, and git-ignored.
- A failed build leaves the live site unchanged. The pipeline then emails Chris and marks the article `publish_failed`.

## 4. Article states (pipeline)

`planned → researching → drafting → reviewing → translating → ready → proposed → (changes_requested → … → proposed) → approved → publishing → published`, plus `held`, `needs_attention` (stuck after the fix rounds or a failed check) and `publish_failed`.

- **Timing:** production starts 4 days before `publish_at`. The proposal email goes out at `publish_at − 24 h`, or as soon as the article is ready if that is later. Publication happens at `max(publish_at, proposal_sent_at + 24 h)`, unless the article is held or changes were requested.
- **The proposal email to Chris** (the `ARTICLES_REVIEW_TO` setting, default the `DIGEST_TO` recipients) contains the full English text, the planned publication time (Zurich time), the sources, and three signed links:
  - **Publish now**
  - **Hold**
  - **Suggest changes**: opens a small page on the app host with the article and a text box.

  Suggestions trigger a revision and a fresh fact check, then a new proposal email. The 24-hour clock restarts from that email (decision: Chris always sees the version that goes out).
- After publishing, the article is checked live, Chris gets a short "Published" email with the links, and Bing is pinged through IndexNow (key `db4ff15a4e2f78e09e2d5d2021e47cd3`, file `/db4ff15a4e2f78e09e2d5d2021e47cd3.txt` in `site/public/`).

## 5. Topic queue: `content/articles/plan.yaml`

```yaml
- key: spouse-facilitated
  kind: article
  category: eligibility
  publish_at: 2026-11-16T07:00:00+01:00
  title: "Married to a Swiss citizen? Facilitated naturalisation explained"
  brief: >
    Who it is for, what this article must answer, and its angle.
  outline: ["...", "..."]           # suggested sections
  must_cover: ["...", "..."]        # facts the article must state, each backed by a source
  sources:                          # seed sources, checked to be fetchable as text
    - title: "..."
      url: "https://..."
  related: [overview, calculator]
  links_to: [dual-citizenship]      # article keys it may link to once they are live
  canton: ag                        # canton guides only
```

The pipeline imports new keys from the plan into the database on each run. It never changes an article that is already in production because the plan changed, and a changed `publish_at` only applies while the article is still `planned`.

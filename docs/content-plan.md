# Viapunt content plan: articles, canton guides and free tools

Written 7 November 2026. Status: proposal, awaiting Chris's decisions (end of file).

## Where we start

- The guide site has 15 guide pages and 10 FAQs, each in 8 languages (fr, it, pt, es, sq, tr are machine translations still awaiting native review). Almost all of it is about Zurich.
- The Viapunt Pass is sold for Zurich **and** Rest of Switzerland, but there is no guide page for any other canton.
- Traffic: about 5 visitors a day (digest, week of 2 November); Google sends the odd visit. The domain is four days old to Google, so links and fresh pages matter most now.
- What ranks today for "Swiss citizenship test" style searches is mostly question-bank apps and practice sites (for example the "Einbürgerung Schweiz" app, open-exam-prep.com) plus spammy pages. Few of them explain the **process** calmly, cite official sources, or write in the languages applicants actually speak.

## How Viapunt can stand out

1. **Sourced and dated.** Every page shows "Checked on <date>" and links to the official source (SEM, fedlex, canton, commune). Spam pages and apps don't do this.
2. **Real situations, not generic explainers.** Each article answers one question an applicant actually has: "I'm married to a Swiss citizen", "Can I keep my passport?", "I moved canton".
3. **Applicants' own languages.** Portuguese, Albanian, Turkish, Italian and Spanish speakers are large applicant groups with very little good content in their language. This is the strongest differentiator, but only once a native speaker has checked the text.
4. **Free tools people bookmark:** the residence calculator (already live), an eligibility checker, a printable document checklist, and a glossary of the German admin words.
5. **The calm guide voice** (standing rule: information first; every page ends with a soft route to the free questions, never a hard sell).

## Part 1: an Articles section (the blog)

Built into the Astro site rather than a separate blog tool, so it shares the design, languages and sitemap.

- Address: `/en/articles/<slug>/`, German `/de/ratgeber/<slug>/`. Index page lists posts by category, and the home page gets a "Latest articles" row.
- New content collection `site/src/content/articles/<lang>/` with frontmatter: title, description, date, updated, category, sources, related guide pages, FAQ items.
- Each article: about 900–1,300 words, a short "In brief" box at the top, a sources box, a 3–5 question FAQ at the end (AI assistants quote these), links to 2–3 guide pages, and the soft call to action to `/try`.
- Byline "By the Viapunt team" (same decision as the SST blog: no invented persona).
- Technical: Article + BreadcrumbList structured data with `dateModified`, an RSS feed, `logo` added to the Organization data (this also helps the logo in search), hreflang only between languages that exist.
- Five categories: **Eligibility & your situation**, **Cantons**, **The knowledge test**, **Documents & process**, **After naturalisation**.

### First 12 articles (one a week from 16 November)

| # | Title (working) | Category | Why |
|---|---|---|---|
| 1 | Married to a Swiss citizen? Facilitated naturalisation explained | Eligibility | Very common search; federal route, so it works for every canton |
| 2 | Can I keep my passport? Dual citizenship for the main nationalities in Switzerland | After | Top question in every applicant language; one sourced section per country |
| 3 | How your years in Switzerland are counted (years 8–18, permits, time abroad) | Eligibility | Feeds the calculator; frequent confusion |
| 4 | Preparing for the Zurich knowledge test in four weeks | Knowledge test | Ties directly to the product; links to the six topic pages |
| 5 | What "successful integration" means: debts, welfare, criminal record | Eligibility | People worry about this and rarely find a plain answer |
| 6 | Moving canton or commune during your application | Process | A real trap; links to the canton pages as they appear |
| 7 | Children and naturalisation: including them, and when they're assessed on their own | Eligibility | Families are a large share of applicants |
| 8 | B1 spoken, A2 written: what the language requirement really asks | Process | Links to the language-certificates page |
| 9 | The naturalisation interview: what people are asked, and how to prepare | Knowledge test | Builds on the existing interview page; the interview page already gets visits |
| 10 | C permit or Swiss passport: what changes when you naturalise | After | Captures people still deciding whether to apply |
| 11 | Third generation: the simplified route for grandchildren of immigrants | Eligibility | Small group, almost no competition |
| 12 | Seven mistakes that delay a Swiss citizenship application | Process | Evergreen; good for sharing in forums |

Later: a "What changed in 2027" post each January, and short news posts whenever a canton changes its test or fees.

## Part 2: canton guides (bigger than the blog)

People search by canton ("Einbürgerung Aargau", "naturalisation Vaud"). One evergreen guide page per canton, from official canton sources (catalogues may be read, never copied: D-063). Each page covers residence rules, test format, fees and steps, and links to the Rest of Switzerland pass.

Order: German-speaking cantons first, because the test language matches what the app teaches. Proposed: **Aargau** (published practice catalogue), **Bern**, **Basel-Stadt**, **Lucerne**, **St Gallen**. Then **Vaud** and **Geneva** in French and English, once a French reader can check them. Pace: one canton every two weeks, alternating with articles.

## Part 3: free tools

1. **Glossary of admin German** (we already have 40 terms in 7 languages in `content/glossary`). Make it a public page: "Betreibungsregisterauszug: what it is and where to get it". Cheap, unique, and it ranks for long, specific searches.
2. **Eligibility checker:** extend the calculator with permit, canton and married-to-a-Swiss questions, ending in "your likely route" plus links.
3. **Printable Zurich document checklist** (one A4 page per route).

## Part 4: getting known outside the site (most important for a new domain)

A new domain gets most of its early search ranking from links. In order of value:

- **Integration offices and language schools** (cantonal Fachstellen Integration, B1 course providers): offer the glossary and the checklist as free resources they can link to.
- **Diaspora associations and their Facebook groups** (Portuguese, Albanian, Kosovar, Turkish, Italian clubs): share the articles in their language once they're reviewed.
- **Expat communities** (English Forum Switzerland, r/askswitzerland): answer questions properly and link only where a page truly answers it.
- **Media pitches:** Newly Swissed, swissinfo, local papers. Angle: "a free, sourced guide to naturalisation in eight languages".
- **Swiss Science Tutors website:** one link from the About page or footer ("our naturalisation guide").

## Weekly routine (about 15 minutes of Chris's time, like the SST blog)

| When | Claude | Chris |
|---|---|---|
| Once a month | Drafts the next four articles (English + German), with sources and FAQ | 5 min to start the session |
| Each week, by Thursday | Article ready in a branch, preview on staging | 10 min: check facts, approve |
| On approval | Deploys to production, requests indexing (or gives the Search Console steps) | OK the deploy |
| Every 4 weeks | Reviews Search Console queries and the help-chat questions; adjusts the list | Read a one-page summary |

The help chat on the guide site is our equivalent of the SST enquiry messages: the questions people type there (aggregated, no personal data) are the best source for new article topics.

## Measuring

- Search Console: impressions and clicks for articles and canton pages. Check at 4 weeks (around 14 Dec) and 8 weeks (around 11 Jan).
- Digest: visitors, referrers, `/try` starts, sign-ups.
- Target for 8 weeks: 50+ visitors a day and the first sign-ups that come from search.

## Decisions for Chris

1. Section name: "Articles" / "Ratgeber" (proposed), or "Blog"?
2. Pace: one article a week plus one canton every two weeks?
3. First cantons: Aargau, Bern, Basel-Stadt, Lucerne, St Gallen?
4. Translations: English + German at launch; other languages only after native review. Who could review Portuguese, Albanian and Turkish?
5. Standing OK to deploy approved articles to production, or one OK per article?

## Build order once approved

1. Articles collection, index, structured data, RSS, Organization logo (about one session).
2. Articles 1 and 2 (English + German).
3. Glossary page (content already exists).
4. Aargau canton guide.
5. Then the weekly routine.

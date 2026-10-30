# Swiss citizenship test trainer – build plan

Oct 30, 2026 · @Chris

A free, multilingual guide website that leads to a paid web app for the naturalisation knowledge test, starting with the canton of Zurich. Its selling point: learners first understand every question and answer in their own language, then practise the same questions in German until they can pass the test in its real format. The app is built by reusing the SST maths web app as far as possible; learners are adults, so the parent and child features are removed.

## Scope

The first release covers the Zurich knowledge test, a guide site in German and English with key pages in the launch languages, and a paid Civics Pass; Aargau follows in the next phase.

**In the first release**

- A guide website: how naturalisation works, step by step for Zurich, fees, the knowledge test, language certificates, a residence-years calculator and free sample questions.
- A learning app for Zurich's knowledge test (Grundkenntnistest): about 350 original questions, each with an explanation, in German and the launch languages.
- Three ways to study: Learn (own language beside German), Practise (adaptive, moving to German only) and Mock test (German only, real format and timing).
- An "Explain this" button that answers questions about the current item in the learner's language.
- Sign-in, one-off payment by card or TWINT, and an admin area.

**Later phases**

- Aargau, then Vaud and Geneva (where the test is in French).
- Commune pages and commune-specific questions.
- German audio for every question.
- Spoken language practice for the fide test and the commune interview.

**Not in scope**

- Individual legal advice on applications, refusals or appeals.
- Any claim of official status or link to the authorities beyond citing their published pages.

## Reusing the SST maths app

Start from a copy of the near-ready SST maths web app and keep its stack, conventions and infrastructure; the coding agent's first task is an inventory of that app (REUSE.md) mapping every module to keep, adapt or remove, for Chris to approve before any code changes.

| Area | Action | Notes |
| --- | --- | --- |
| Stack, project layout, conventions, CI, Docker and deployment scripts | Keep | Same Swiss hosting (Infomaniak); a separate staging and production stack and domain |
| Sign-in, sessions, security settings | Adapt | Single adult accounts; email sign-in link as the default (see Learners and accounts) |
| Parent and student roles, under-18 rules, parent summaries, minors' safeguarding queue | Remove | Learners are adults (16 and over) |
| Homework photo upload and image screening | Remove | Not needed |
| Stripe checkout, webhooks, entitlements, TWINT | Adapt | One-off payment per canton pass instead of subscriptions |
| AI call module (model choice, caching, limits, cost log), versioned prompts, off-topic gatekeeper | Keep | Used for "Explain this" and the content pipeline |
| Question bank, practice mode, mastery tracking, timed tests | Adapt | New question model with canton, category, sources and translations |
| Maths rendering and maths checks | Remove | Replaced by source checks |
| Admin area, cost dashboard, error tracking, backups | Keep | Add content review and translation status screens |
| Interface translations (i18n) | Adapt | More interface languages; question translations are content, not interface text |
| Guide website | New | Pre-rendered pages for search engines (see Guide website) |
| Translation pipeline and glossary | New | See Languages |

Use a copy, not a shared library, for now: record the SST commit the copy was taken from in DECISIONS.md, and list in REUSE.md the modules worth sharing later, so fixes can be carried across by hand until then.

## Learners and accounts

One kind of account: an adult learner who signs up, pays and studies for themselves. Aargau tests from age 16, so accounts are open from 16 with a self-declared age check and no parental flows.

- **Sign-in:** a one-time email link by default (single use, valid 15 minutes); passwords optional; Google and Apple sign-in as an open decision.
- **Collected:** email, interface language, study language, canton, progress, and payment status. Nothing else.
- **Never asked:** nationality, permit type, date of birth, address or anything about the person's application. Origin and residence status are sensitive in combination, and the app does not need them.
- **Residence calculator:** runs in the browser only; nothing entered is sent or stored.
- **AI explanations:** only the question text and the learner's typed question go to the AI provider, never the email or name. The privacy notice says the AI provider processes this outside Switzerland.
- **Deletion:** learners can delete their account and data themselves; billing records are kept as required by law.
- **Roles:** Learner and Admin only. Reviewer (a translator or fact-checker who can see and approve content for one language or canton) is added in Phase 1.

## Question bank

Every question is written by SST, not copied: the cantons' catalogues are protected and may not be reused commercially without consent, but the facts they test are free to teach. If a canton later grants a licence, its official questions can be added as a separate, labelled set.

**Coverage**

- **Zurich (Phase 1):** about 350 questions mirroring the balance of the official catalogue, which has 274 federal, 56 cantonal and 20 communal questions. Mock tests: 50 questions in 60 minutes, four options each.
- **Aargau (Phase 2):** about 330 questions across its five categories: Demokratie/Föderalismus, Sozialstaat, Rechtsstaat, Geschichte and Zivilgesellschaft. Mock tests: 45 questions in 40 minutes, pass mark 34. Aargau's pool is not public; confirm the question format from the official practice test before writing.
- **Federal questions are shared** between cantons where the topic matches; canton and commune questions are separate.

**Each question stores**

| Field | Content |
| --- | --- |
| ID and version | Stable ID; the version rises with every change |
| Scope | Federal, canton (ZH, AG) or commune |
| Category | The canton's own category names |
| German text | Question, four options, the correct option, a short explanation |
| Sources | At least one official page (admin.ch, ch.ch, the canton or commune), with the date it was checked |
| Glossary terms | Key terms in the question (e.g. Ständerat, Gemeindeversammlung) linked to the glossary |
| Translations | One entry per language, tied to the German version it translates |
| Status | Draft, in review, approved or retired |

**How a question goes live**

1. The topic list is drawn from the official catalogue's subjects and the federal and cantonal constitutions.
2. The pipeline drafts questions in German, then a second, independent pass answers each one without seeing the key; both must agree.
3. A source check confirms the answer against the cited official page.
4. Chris or a paid reviewer approves it in the admin area.
5. Only then is it translated (see Languages).
6. Learner reports send a question back to review; a yearly review re-checks every source, because Zurich updates its catalogue each year.

Content lives as versioned files in the repository (the master copy), imported into the database on deploy, so every change is tracked.

## Languages

The selling point is understanding first, then German: a learner meets each question in their own language beside the German, and is gradually weaned onto German only, the language of the Zurich and Aargau tests. Translations are always labelled as study aids; the test itself is in German.

**Launch languages (default, to confirm):** English, French, Italian, Portuguese, Spanish, Albanian and Turkish, with German as the master. These cover the largest groups becoming Swiss after Germans: Italians, French, Kosovars, Portuguese, Turks, Spaniards and the British. Later: Bosnian/Croatian/Serbian, Macedonian, Tamil, Ukrainian and Arabic (which needs right-to-left layout).

**Study modes for each question**

| Mode | What the learner sees |
| --- | --- |
| Own language | Question and answers in their language, the German underneath in smaller text |
| Side by side | German and their language with equal weight |
| German with help | German only; key terms are underlined and show their translation and a short note when tapped |
| German only | Exactly as in the test |

Progress is tracked per question and mode: a question counts as understood when answered correctly in the learner's language, and as known only when answered correctly twice, on different days, in German only.

**Translation pipeline**

1. Translate only questions whose German version is approved.
2. Machine-translate with a fixed glossary of official terms; take the official French, Italian and English names of institutions from TERMDAT, the federal terminology database, where they exist.
3. Translate back into German in an independent pass and flag any difference in meaning.
4. A native-speaker reviewer checks the first 100 questions of each language in full, then a 10% sample of each batch plus every flagged item.
5. Each translation records the German version it came from; when the German changes, the translation is hidden until refreshed.
6. Learners can report a translation problem from any question.

Interface text (buttons, menus) uses the app's existing translation system and is available in every launch language.

## Learning app

The app has three study areas and an "Explain this" helper, all built on the SST practice engine.

**Learn**

- Topic by topic, in the order of the official catalogue's subjects (for Zurich: Confederation, canton, commune).
- Each card shows the question, the correct answer and a two- or three-sentence explanation in the chosen study mode.

**Practise**

- Adaptive questions with spaced repetition, weighted towards weak topics.
- The app moves each question from own language towards German only as the learner gets it right; the learner can always step back a mode.
- A mastery bar per topic and an overall readiness estimate, labelled "practice estimate, not an official result".

**Mock test**

- German only, the real number of questions and time limit (Zurich: 50 in 60 minutes), with a countdown and no help.
- Questions drawn in the same proportions as the official test where known.
- Afterwards: score, pass or fail against the pass mark (Zurich's 30 of 50 is from a press report; confirm it), and a review of each wrong answer in the learner's language.

**Explain this**

- A button on every question in Learn and Practise (not in mock tests) that opens a short chat about that question, answered in the learner's language.
- Reuses the SST AI module and gatekeeper: topic-scoped, short answers, no legal advice about the learner's own application, about 20 messages a day.

**Also**

- A glossary of key terms with translations and short notes.
- Works well on phones and installs as an app from the browser, as the SST app does.
- Flag a question as wrong or unclear; flags go to the admin review queue.

## Guide website

The guide site is where learners find the service, so it must be genuinely useful, fast and easy for search engines to read. It lives at the main domain; the app at `app.` on the same domain.

| Page | Purpose | Languages at launch |
| --- | --- | --- |
| Becoming Swiss: overview | Federal requirements, the order of steps, how long it takes | All launch languages |
| Zurich, step by step | Residence rules, documents, fees, timeline, where to apply | German, English |
| The Zurich knowledge test | Format, topics, how to prepare, link to the official catalogue | All launch languages |
| Language certificates | Which ones count, levels, prices, where to take them | German, English |
| Fees | Federal, cantonal and typical communal fees | German, English |
| Residence-years calculator | Counts the years, with ages 8 to 18 counting double; runs in the browser only | All launch languages |
| Free practice | 30 sample questions with translations, no account needed; one free mock test after email sign-up | All launch languages |
| Frequently asked questions | Short answers that link to the pages above | All launch languages |

**Rules for every page**

- Cites the official pages it relies on, with a "last checked" date; a yearly review is scheduled for each page.
- Footer notice: independent service, not connected to any federal, cantonal or communal authority; general information, not legal advice.
- No Swiss or cantonal coats of arms, no "official" wording, nothing that imitates government websites.
- Each page ends with a clear route into the app: try the free questions, then the Civics Pass.

**Technical**

- Pre-rendered HTML pages (a static site generator, or pre-rendering in the app's own framework, whichever fits the SST stack), so search engines see the full text.
- Content as Markdown files per language in the repository, with language versions linked to each other (hreflang), a sitemap and FAQ markup.
- Self-hosted analytics without cookies, so no consent banner is needed.
- Pages load quickly on a phone; check with Lighthouse before launch.

## Payments and pricing

One simple purchase: a Civics Pass per canton, paid once, with free practice beforehand to show the value.

| Product | Price (CHF) | What it includes | Stripe lookup key |
| --- | --- | --- | --- |
| Free | 0 | Guide site, 30 sample questions per canton in every language, one mock test after email sign-up | – |
| Civics Pass, one canton | 29 | All questions and study modes for that canton, unlimited mock tests, Explain this, every language, 6 months' access | `civics_pass_zh`, `civics_pass_ag` |
| Extension | 9 | Three more months | `civics_extension` |

- Stripe Checkout in one-off payment mode, card and TWINT, reusing the SST integration; access starts when the webhook confirms payment.
- Prices live in Stripe and are looked up by key, never hard-coded; shown in CHF including VAT if SST is VAT-registered.
- A refund within 14 days if fewer than 50 questions have been studied (default, to confirm).
- Couple discount: a second pass for a partner at half price (open decision).

## Build phases

Zurich goes live at gate B; Aargau and the French cantons follow. Phases run in order; each gate needs Chris's sign-off.

| Phase | Scope | Gate at the end |
| --- | --- | --- |
| Phase 0: Copy and strip | Inventory approved; adult accounts; one-off payments | Gate A: staging works end to end |
| Phase 1: Zurich launch | 350 questions; 8 languages; Learn, Practise, Mock test; guide site, payments | Gate B (public launch): content and test panel done, brand and terms ready |
| Phase 2: Aargau and growth | Aargau questions; commune pages; more languages; German audio | Gate C: Zurich sales and pass reports reviewed |
| Phase 3: French-speaking cantons and speaking | Vaud and Geneva; fide speaking pilot; interview practice | None |

Each phase ends at a gate Chris signs off; nothing is sold before gate B. A phase is done when every box below it is ticked.

**Phase 0: Copy and strip** (gate A: staging works end to end)

- [ ] REUSE.md written and approved.
- [ ] New repository from a copy of the SST app; CI and tests pass after the removals.
- [ ] Learner and admin accounts with email sign-in links.
- [ ] Stripe one-off payments working in test mode, with entitlements per canton.
- [ ] Staging site live on Infomaniak with its own domain, TLS and nightly backups.

**Phase 1: Zurich launch** (gate B: content reviewed, test panel done, brand and terms ready)

- [ ] Question model, import from repository files, and the review queue in the admin area.
- [ ] Content pipeline scripts: draft, independent answer, source check, translation, back-translation.
- [ ] About 350 Zurich questions approved in German, translated and reviewed in the launch languages.
- [ ] Learn, Practise and Mock test, with the four study modes and progress tracking.
- [ ] Explain this, with limits and cost logging.
- [ ] Guide site pages, the residence calculator and free practice, in the languages listed under Guide website.
- [ ] Terms, privacy notice and independence notice published.
- [ ] Test panel of 15–20 people completed and their findings fixed.

**Phase 2: Aargau and growth** (gate C: Zurich sales and learners' pass reports reviewed)

- [ ] Aargau questions in its five categories and its mock test format.
- [ ] Commune pages for the 30–50 communes with the most international residents.
- [ ] More languages (Bosnian/Croatian/Serbian, Macedonian, Tamil, Ukrainian).
- [ ] German audio for every question.

**Phase 3: French-speaking cantons and speaking**

- [ ] Vaud and Geneva, with French as the test language.
- [ ] A pilot of spoken fide practice and commune interview practice.

## Testing and quality

The main risk is a wrong fact or a misleading translation, so content checks matter as much as code tests.

**Content**

- An automated check on every build: each question has a source and a checked date under a year old, four options and exactly one correct answer, and a translation for every launch language (or is marked as not yet translated).
- A weekly link check on all cited sources; a broken or changed page sends the question to review.
- A test panel of 15–20 people who have recently taken the Zurich test, or are about to, comparing the app's questions and difficulty with the real test.

**Code**

- Unit and integration tests carried over from the SST app, plus new ones for the question import, study-mode progression, mock test generation (counts, proportions, timer, scoring) and payment entitlements.
- End-to-end tests for: free questions, sign-up, a mock test, checkout in Stripe test mode, and access expiry.
- Accessibility: keyboard use, screen readers and contrast on the main screens.
- Guide site: Lighthouse scores of 90 or more for performance, accessibility and SEO on phone settings, and valid hreflang links.

## Instructions for the coding agent

Read this plan in full, then the SST maths app's code, before writing anything.

1. Save this plan as `PLAN.md` in the new repository and keep `PROGRESS.md` (done and next) and `DECISIONS.md` (every assumption, dated) up to date.
2. First task: write `REUSE.md`, an inventory of the SST maths app listing every module as keep, adapt or remove, with reasons, and the modules worth sharing later. Stop and wait for Chris's approval.
3. Create the new repository from a copy of the SST app at a tagged commit; record the commit in `DECISIONS.md`. Do not build a shared library yet.
4. Keep the SST app's stack, structure and conventions. Follow its existing patterns rather than introducing new frameworks; if the guide site needs a static site generator, propose it in `DECISIONS.md` first.
5. Remove the parent and student roles, under-18 rules, parent summaries, homework photos and image screening, and maths-specific rendering and checks, with their tests.
6. Every AI call goes through the existing AI module, with its limits and cost logging. The content pipeline (drafting, independent answer, translation, back-translation) runs as command-line scripts using the batch API, and never overwrites a translation a reviewer has approved.
7. Question content and guide pages are versioned files in the repository; the database is filled from them on deploy.
8. Never copy text from cantonal question catalogues or test series into the repository, prompts or generated content. Use them only to list topics.
9. Never collect nationality, permit type, date of birth or address. The residence calculator runs only in the browser.
10. No Swiss or cantonal coats of arms, no "official" wording, and the independence notice in every footer.
11. Interface text in British English, German, French, Italian and the launch languages; amounts in CHF with Swiss number formatting.
12. Never commit secrets; use Stripe test mode and the staging AI key until Chris approves go-live. Ask before adding a paid service or any new third party that receives personal data.
13. No AI attribution anywhere: no "generated by" lines or co-author trailers in code, documentation, interface text or commit messages.
14. End each phase with a running staging site, an updated README and a short demo script Chris can follow.

## Open decisions

Each has a default the coding agent may use, recorded in DECISIONS.md, if Chris has not decided by the time it is needed.

- [ ] Brand name and domain: neutral, not official-sounding, checked against the trademark register and existing apps. Default: a working name in the code only. Before Phase 1.
- [ ] Launch languages. Default: English, French, Italian, Portuguese, Spanish, Albanian, Turkish. Phase 1.
- [ ] Native-speaker reviewers for each launch language, and their pay per batch. Phase 1.
- [ ] Ask the Zurich Gemeindeamt (grundkenntnistest@ji.zh.ch) and the Aargau Staatskanzlei whether they would license their questions. If yes, the official questions with translations become the main selling point. Default: original questions only.
- [ ] Civics Pass price and access period. Default: CHF 29 for 6 months, extension CHF 9 for 3 months. Phase 1.
- [ ] Couple discount. Default: none at launch.
- [ ] Google and Apple sign-in. Default: email link only.
- [ ] Zurich pass mark (30 of 50 in a 2022 press report) and Aargau's question format: confirm with the cantons before the mock tests go live.
- [ ] VAT on digital education products, and SST's purpose clause covering this activity: accountant and notary.
- [ ] Store versions for the App Store and Google Play. Default: installable web app only, reviewed after launch.

## References

Official pages to build the content from (opened October 2026), and the market review behind this plan.

- [Zurich knowledge test and question catalogue](https://www.zh.ch/de/migration-integration/einbuergerung/grundkenntnistest.html), with its [terms of use](https://www.zh.ch/de/nutzungshinweise.html)
- [Aargau test procedure](https://www.ag.ch/media/kanton-aargau/dvi/dokumente/arp/buergerrecht-und-personenstand/einbuergerungen/handbuch-ordentliche-einbuergerungen/handbuch-anhang-2-hinweise-testablauf.pdf) and [legal notices](https://www.ag.ch/de/ueber-uns/rechtliche-hinweise)
- [ch.ch: naturalisation](https://www.ch.ch/de/einbuergerung)
- [SEM: recognised language certificates](https://www.ejpd.admin.ch/dam/sem/de/data/integration/themen/sprache/anerkannte-sprachzertifikate.pdf.download.pdf/anerkannte-sprachzertifikate-d.pdf)
- [TERMDAT, the federal terminology database](https://www.termdat.bk.admin.ch)
- [Copyright Act, Art. 5 (works not protected)](https://www.droit-bilingue.ch/en-de/2/23/231.1-5-8.html)
- [Coat of Arms Protection Act](https://wipo.int/wipolex/en/legislation/details/16777)
- [Swiss naturalisation prep – market review](https://claude.ai/artifact/SQ7qNANvkQCtmGrWUv3cns)

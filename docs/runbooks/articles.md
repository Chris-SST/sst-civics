# Articles: the automated pipeline

The worker writes, fact-checks, translates and publishes the articles and canton guides listed
in `content/articles/plan.yaml` (D-073). Chris gets each proposed article by email 24 hours
before publication; if he does nothing it goes out. The interface with the site and the site
builder is [docs/articles-contract.md](../articles-contract.md); this page is about running it.

## How it works

Every 15 minutes the worker's `articles_tick` job (only when `ARTICLES_ENABLED=true`):

1. **Imports the plan.** New keys become `planned`. A `planned` article takes every change of
   its plan entry, `publish_at` included; once production has started, plan changes no longer
   touch it. A `planned` key removed from the plan is deleted (only when the whole file parses
   without errors). Invalid entries are skipped and logged.
2. **Starts production** 4 days before `publish_at` (`ARTICLES_LEAD_DAYS`), as its own job
   (`produce_article`, up to an hour, never retried automatically). The database claim makes
   sure one article is never produced twice at once.
   - *Research:* the plan's seed sources are fetched (`app/content/fetch.py`); at least two
     must be readable. The model gets only these pages and may cite only these pages.
   - *Write* (`claude-opus-5-5`, `prompts/articles/write`): frontmatter fields and the
     Markdown body as structured output.
   - *Deterministic checks* (`app/articles/validate.py`): lengths, slug, 3 to 5 summary
     sentences and FAQ items, 2 to 12 sources that were read, guide and article
     placeholders, no H1, HTML or images, the word range, no "official" wording. Problems go
     back to the writer (`prompts/articles/fix`), at most twice.
   - *Fact review* by an independent call (`claude-opus-5-5`, `prompts/articles/review`)
     with the same source excerpts: findings with claim, problem, severity and fix. Any
     blocker or major finding gets a fix round; after two fix rounds it stops as
     `needs_attention` and Chris gets an email.
   - *Translations* into `ARTICLES_LANGUAGES` (`claude-sonnet-5-5`,
     `prompts/articles/translate`, with the `content/glossary` terms, a localised slug and every
     placeholder unchanged), each checked against the English structure and reviewed by an
     independent call (`claude-opus-5-5`, `prompts/articles/translation_review`), with one fix
     round. A language that still fails is skipped and noted; English is never held back.
   - Each run stops when it has cost more than `ARTICLES_COST_CAP_CHF`, or when this month's
     AI spend reaches `AI_MONTHLY_BUDGET_CHF`.
3. **Sends the proposal** at `publish_at − 24 h`, or as soon as the article is ready if that is
   later, to `ARTICLES_REVIEW_TO` (else `DIGEST_TO`, else every admin): the full English text,
   the planned time in Zurich time, sources read, translation status, the fact check's minor
   notes, and three links: **Publish now**, **Hold**, **Suggest changes**. They open a page
   on the app host (`/api/articles/review/<token>`): a signed link, valid until 14 days after
   the latest publication; opening it changes nothing, the page has the buttons.
   - *Suggest changes* stores the text, revises the article with it as top priority,
     fact-checks and translates again, and sends a new proposal; the 24-hour clock restarts
     from that email.
   - *Hold* stops everything until Publish now or a new suggestion.
4. **Publishes** at `max(publish_at, proposal_sent_at + 24 h)` as its own job
   (`publish_article`): it writes every passing language to `ARTICLES_DIR/<lang>/<slug>.md`
   (atomically; files of languages that no longer pass, or of an old slug, are removed),
   writes `ARTICLES_DIR/.build-request`, and waits for the builder's status file
   (`SITEBUILD_STATUS_FILE`) to report a finished build at or after the request. Then it
   checks every page on `GUIDE_BASE_URL` for HTTP 200, marks the article `published`, emails
   Chris the links and, in production, pings IndexNow. A failed build, a timeout
   (`ARTICLES_BUILD_TIMEOUT_MINUTES`) or a failed live check is `publish_failed` with an email;
   the live site stays as it was.
5. **Corrections after publication:** within 14 days Chris can use Suggest changes on the same
   page. The article is revised and proposed again; 24 hours after that email the new version
   replaces the live one, with `published` kept and `updated` set to the day.

The daily digest has an "Articles" section: published yesterday, the next one with its date,
what is waiting on Chris, held articles, and `needs_attention` or `publish_failed` as actions.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `ARTICLES_ENABLED` | `false` | The 15-minute tick and the two jobs run only when true. The CLI works either way. |
| `ARTICLES_DIR` | `/srv/articles` | Published files and the build request. Worker: read-write. |
| `SITEBUILD_STATUS_FILE` | `/srv/site-releases/build-status.json` | The builder's status. Worker: read-only. |
| `ARTICLES_REVIEW_TO` | empty | Proposal recipients, comma-separated; empty means the digest recipients. |
| `ARTICLES_WRITE_MODEL` | `claude-opus-5-5` | Writing and fix rounds. |
| `ARTICLES_REVIEW_MODEL` | `claude-opus-5-5` | Independent fact review. |
| `ARTICLES_TRANSLATE_MODEL` | `claude-sonnet-5-5` | Translations. |
| `ARTICLES_TRANSLATION_REVIEW_MODEL` | `claude-opus-5-5` | Independent translation review. |
| `ARTICLES_EFFORT` | `high` | Effort for writing, review and fixes. |
| `ARTICLES_TRANSLATE_EFFORT` | `medium` | Effort for translation and its review. |
| `ARTICLES_COST_CAP_CHF` | `6` | Per production run (the first version, or one revision). |
| `ARTICLES_LEAD_DAYS` | `4` | Production starts this long before `publish_at`. |
| `ARTICLES_PROPOSAL_HOURS` | `24` | Proposal before publication, and the minimum wait after it. |
| `ARTICLES_LANGUAGES` | `de,fr,it,pt,es,sq,tr` | Translation languages; English always exists. |
| `ARTICLES_BUILD_TIMEOUT_MINUTES` | `20` | Longest wait for the builder. |
| `ARTICLES_INDEXNOW` | `true` | Ping IndexNow after publishing (only when `APP_ENV=production`). |

Also used: `APP_BASE_URL` (the review links), `GUIDE_BASE_URL` (live check, IndexNow host),
`SECRET_KEY` (signs the links; changing it invalidates every link sent), `ANTHROPIC_API_KEY`,
`AI_MONTHLY_BUDGET_CHF`, the email settings.

The worker needs `ARTICLES_DIR` mounted read-write (owned by uid 10001) and the builder's
`site-releases` directory read-only, so that `SITEBUILD_STATUS_FILE` exists inside it.

## Commands

On the server, prefix each with
`docker compose -p civics-prod -f infra/docker-compose.yml --env-file .env exec worker`
(staging: `-p civics-staging`).

```bash
python -m scripts.articles list                    # every article, state, date, cost
python -m scripts.articles import-plan             # import the plan now
python -m scripts.articles produce <key> [--force] # produce now (--force: again, any state)
python -m scripts.articles propose <key>           # send the proposal email now
python -m scripts.articles publish <key>           # publish now and wait for the build
python -m scripts.articles hold <key>
python -m scripts.articles unpublish <key>         # remove the files, rebuild, hold
python -m scripts.articles preview <key> --out /tmp/articles   # files for a local site build
python -m scripts.articles tick                    # one tick by hand
```

### A dry run

`--dry-run` (before or after the command) makes no AI call and changes nothing:

```bash
python -m scripts.articles --dry-run import-plan   # validate the plan file only
python -m scripts.articles --dry-run tick          # what would happen now
python -m scripts.articles --dry-run produce spouse-facilitated   # placeholder text, checked
python -m scripts.articles --dry-run propose spouse-facilitated   # print the email
python -m scripts.articles --dry-run publish spouse-facilitated   # list the files it would write
```

To see the site with a real or placeholder article locally:
`python -m scripts.articles preview <key> --out var/articles-preview` (placeholder English when
the article has no text yet, or with `--dry-run`), then build the site with
`ARTICLES_DIR=var/articles-preview`.

A first live test on staging: set `ARTICLES_ENABLED=false`, `ARTICLES_REVIEW_TO` to your own
address, then `produce <key>` and `propose <key>` by hand, check the email and the review page,
then `publish <key>`.

## Pausing

- **Everything:** set `ARTICLES_ENABLED=false` and restart the worker. Nothing is produced,
  proposed or published; the review page still records Chris's choices, and they are acted on
  once it is switched on again.
- **One article:** `hold <key>` (or the Hold link). Publish now or a suggestion releases it.
- **Stop paying for one article:** a held or `needs_attention` article makes no AI calls.

## Unpublishing

`python -m scripts.articles unpublish <key>` deletes the article's files in every language,
writes a build request and puts the article on hold. By hand, the same is: delete
`ARTICLES_DIR/*/<slug>.md` for the article (the `key:` line in each file's frontmatter names
it), then write a fresh build request:

```bash
echo "{\"requested_at\": \"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\", \"reason\": \"unpublish by hand\"}" \
  > /srv/articles/.build-request
```

Then `hold <key>`, or the next tick may publish it again if it is still due.

## When something goes wrong

- **needs_attention:** the email gives the reason (fact review findings, unreadable sources, an
  AI error, the cost cap or the monthly budget). Chris can suggest changes or publish anyway
  from the review page; or fix the plan's sources and run `produce <key> --force`.
- **publish_failed:** the email has the builder's error. Fix the cause, then Publish now on the
  review page or `publish <key>`.
- A production that dies (worker restart) is picked up again after two hours; after three
  attempts it is `needs_attention`.
- The review link says "not valid": a newer email replaced it, `SECRET_KEY` changed, or the
  article was removed from the database. `list` shows the state.

## Costs

Estimated per article at list prices (USD 1 = CHF 0.80), with the default models:

| Step | Model | Typical |
|---|---|---|
| Write (about 16k tokens in, 8k out with reasoning) | Opus | CHF 0.18 |
| Fact review | Opus | CHF 0.14 |
| One fix round and a second review (about every other article) | Opus | CHF 0.30 |
| Seven translations | Sonnet | CHF 0.35 |
| Seven translation reviews | Opus | CHF 0.50 |
| **Total, first version** | | **about CHF 1.30 to 1.60**, at most about CHF 3.50 |
| A revision after a suggestion (fix, review, translations) | | about CHF 1.20 |

At one article a week and one canton guide every two weeks that is about CHF 10 a month. Each
run is capped by `ARTICLES_COST_CAP_CHF` (6) and all AI use by `AI_MONTHLY_BUDGET_CHF`. Every
call is in the AI call log (Admin, Usage) under the purposes `article_write`, `article_review`,
`article_fix`, `article_translate` and `article_translation_review`; `list` shows the total per
article.

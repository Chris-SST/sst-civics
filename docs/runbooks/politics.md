# Politics in your canton: running it

The worker finds, writes, reviews, translates and publishes the canton's politics pages by
itself (D-074): a weekly round-up, an explainer for every cantonal and federal vote, and a
who's who. There is **no proposal email**: a page goes out as soon as it passes the
neutrality and fact reviews, and it appears in the next morning's digest. The interface with
the site is [docs/politics-contract.md](../politics-contract.md) (which extends
[docs/articles-contract.md](../articles-contract.md)); the article pipeline's runbook is
[articles.md](articles.md). The pages share its files, build requests, live check and review
page.

## How it works

Every 15 minutes the worker's `politics_tick` job (only when `POLITICS_ENABLED=true`), for
each canton of `POLITICS_CANTONS`:

1. **Discovery** at the 06:00 tick (Zurich time), before each round-up and on the very first
   run. Every source in `content/politics/sources.yaml` is read with deterministic parsers:
   the JSON behind zh.ch's news overview (government press releases, "Politik & Staat"),
   the Kantonsrat's home page (session bulletins, PDF), the RSS feeds of the city of Zurich
   and Winterthur, the Federal Chancellery's open vote data (LINDAS) and parlament.ch's
   list of the next federal vote. Items go into the table `politics_items` (feeds that show
   only the latest ten items are covered because discovery runs daily). Only if an HTML
   listing yields no dated link at all does a cheap call (`politics/links`) pick the links.
   - **Federal votes**: every proposal of the open data still ahead becomes a vote page
     (`vote-ch-<date>-<slug>`, canton `ch`).
   - **Cantonal votes**: a government press release whose title mentions a vote
     ("Eine kantonale Abstimmungsvorlage am 28. Februar 2027") is read once and a cheap
     call (`politics/proposals`) lists its proposals; each becomes a vote page
     (`vote-zh-<date>-<slug>`).
2. **Round-up** every Friday from 07:00 for Friday to Thursday (`zh-week-<ISO year>-<ISO
   week>`). The stored items of the week (canton and cities) are fetched, a selection call
   (`politics/select`, Sonnet) picks four to six political ones, and the page is written. A
   week with fewer than four is **skipped** (`held`, "quiet week", in the digest, no email).
   A round-up more than 36 hours late is not written.
3. **Vote explainers** are produced `POLITICS_VOTE_LEAD_DAYS` (28) before the vote at 07:00,
   or at once if the vote was found later. Sources: the government's announcement and
   related press releases (cantonal); the Federal Assembly's business text from
   ws.parlament.ch, cited as its Curia Vista page, and parlament.ch's vote page (federal).
   **After the vote** a result check runs once a day for 60 days: federal figures from the
   open data; cantonal figures only when a government page states them (call
   `politics/results`). With a result the page is written again with its "Result" section
   and `result` frontmatter, and republished (`published` kept, `updated` set).
4. **Who's who** on the 1st of each month from 07:00 (and on the first run): the people
   pages are read (Regierungsrat, Kantonsrat members and groups, both city executives with
   their member pages), the seats per party are **counted** from the Kantonsrat's member
   list, and a cheap call (`politics/roster`) lists names, offices and parties. Only when
   these facts differ from the published version is the page written again.
5. **Writing** (Opus, `politics/write_roundup|write_vote|write_whoswho`), the deterministic
   checks (`app/articles/validate.py`: counts, word ranges, the round-up's "Source:" lines
   and closing commune line, the vote's sections, only authority hosts as sources, the
   frontmatter rules the site checks), then the **neutrality review** (Opus,
   `politics/neutrality_review`, one fix round; a blocker or major finding left stops the
   page as `needs_attention`), then the **fact review** (Opus, `politics/fact_review`, two
   fix rounds; if the fixes changed the text, neutrality is checked once more), then the
   translations with their review (the article prompts).
6. **Publication**: `ready` → `approved` → `publishing` → `published`, with the same build
   request and live check as the articles, at `/<lang>/<segment>/<canton>/<slug>/`. No
   "published" email. A failure is `needs_attention` or `publish_failed` with **one** email
   (to `ARTICLES_REVIEW_TO`, else the digest recipients) and an action in the digest.
7. **Practice questions** after each published round-up or vote explainer: two or three
   German questions (Opus, `politics/questions`), an independent answer without the key
   (Sonnet, `politics/question_check`; a question is kept only when it gets the same answer
   and is answerable from the page, has one correct option and is neutral), translations
   into en fr it pt es sq tr (Sonnet, `politics/question_translate`). They are stored in
   `current_affairs_questions` with `expires_at` (round-up: 6 months after its week; vote:
   12 months after the vote). A republished vote replaces its earlier questions.

The digest has a "Politics" section: pages published yesterday (with the English link),
round-ups skipped, the next vote explainers, how many current-affairs questions are live,
and every page that needs action (also on the "To do today" list).

## In the app

Learners whose canton has questions see a "Current affairs (canton of Zurich)" card on their
home page (hidden when there are none) and the page `/practise/current-affairs`. It is free
for everyone. Each question shows the date it refers to and, after answering, links to its
page. Answers are checked by `/api/study/current-affairs/answer` and **not stored**: no
attempt, no progress, so these questions never touch the question bank, catalogue topics,
the free sample set, the mock test or readiness. Expired questions are never served.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `POLITICS_ENABLED` | `false` | The tick and its jobs run only when true. The CLI works either way. |
| `POLITICS_CANTONS` | `zh` | Cantons to cover; each needs a block in `content/politics/sources.yaml`. |
| `POLITICS_COST_CAP_CHF` | `4` | Per production run of one page. |
| `POLITICS_VOTE_LEAD_DAYS` | `28` | Vote explainers go out this long before the vote. |
| `POLITICS_WRITE_MODEL` | `claude-opus-5-5` | Writing and fixes. |
| `POLITICS_REVIEW_MODEL` | `claude-opus-5-5` | Neutrality and fact reviews. |
| `POLITICS_SELECT_MODEL` | `claude-sonnet-5-5` | The week's selection. |
| `POLITICS_EXTRACT_MODEL` | `claude-haiku-5-5` | Links, proposals, results, roster. |
| `POLITICS_QUESTION_MODEL` | `claude-opus-5-5` | The practice questions. |
| `POLITICS_QUESTION_CHECK_MODEL` | `claude-sonnet-5-5` | Their independent check. |

Also used from the article pipeline: `ARTICLES_DIR`, `SITEBUILD_STATUS_FILE`,
`ARTICLES_REVIEW_TO`, `ARTICLES_TRANSLATE_MODEL`, `ARTICLES_TRANSLATION_REVIEW_MODEL`,
`ARTICLES_EFFORT`, `ARTICLES_TRANSLATE_EFFORT`, `ARTICLES_LANGUAGES`,
`ARTICLES_BUILD_TIMEOUT_MINUTES`, `ARTICLES_INDEXNOW`, `GUIDE_BASE_URL`,
`AI_MONTHLY_BUDGET_CHF`. `ARTICLES_ENABLED` does not need to be on for politics.

## Commands

On the server, prefix each with
`docker compose -p civics-prod -f infra/docker-compose.yml --env-file .env exec worker`.

```bash
python -m scripts.politics list                  # every politics page, state, cost, questions
python -m scripts.politics discover              # read all sources now (stores items, creates votes)
python -m scripts.politics roundup               # create this week's round-up now (if due)
python -m scripts.politics produce <key> [--force]
python -m scripts.politics publish <key>         # publish now and wait for the build
python -m scripts.politics questions <key>       # make the practice questions again
python -m scripts.politics tick                  # one tick by hand

python -m scripts.politics --dry-run discover    # read every source, print what it finds; stores nothing
python -m scripts.politics --dry-run tick        # what would happen now
python -m scripts.politics --dry-run produce <key>   # the brief and the sources, no AI
python -m scripts.politics --dry-run publish <key>   # the files it would write
```

Hold, unpublish and preview work through `scripts.articles` with the same key
(`hold <key>`, `unpublish <key>`, `preview <key> --out ...`). A held page makes no AI calls.

A first live test on staging: `POLITICS_ENABLED=false`, `ARTICLES_REVIEW_TO` your address,
then `discover`, `roundup`, `produce zh-week-<y>-<w>`, read the result with
`scripts.articles preview`, then `publish`.

## When something goes wrong

- **needs_attention**: the email gives the reason (a neutrality blocker, fact-review
  findings, too few readable sources, an AI error, the cost cap). Open the review page from
  the email: Suggest changes rewrites the page with your note as top priority and runs both
  reviews again; Publish now publishes the last version as it is. Or
  `produce <key> --force`.
- **Quiet week** (`held`): nothing to do; next Friday comes on its own. To force one,
  `produce <key> --force`.
- **A source stops working**: `--dry-run discover` shows which source returns nothing or an
  error. Fix or drop it in `content/politics/sources.yaml` (the reasons for every page that
  was dropped are listed there). Only the hosts under `item_hosts` may be read and cited.
- **A vote page that should not exist** (a proposal listed wrongly): `scripts.articles hold
  <key>` before its date.

## Costs

Estimated at list prices (USD 1 = CHF 0.80):

| Page | Typical | At most |
|---|---|---|
| Round-up (selection, writing, neutrality, facts, 7 translations and reviews) | CHF 1.40 to 1.90 | CHF 4 (cap) |
| Vote explainer | CHF 1.30 to 1.80, again for the result | CHF 4 per run |
| Who's who check (monthly, cheap model) | CHF 0.02 | |
| Who's who rewrite (rare) | CHF 1.50 | CHF 4 |
| Practice questions (write, check, translate) | CHF 0.15 | |
| Daily discovery (cheap calls only for new vote announcements) | under CHF 0.01 | |

About **CHF 3.50 a week** on average: one round-up (about CHF 1.80 with its questions) and
some 20 to 25 vote pages a year, each written twice (before the vote and with the result),
about CHF 1.60 a week spread over the year, with peaks of CHF 8 to 12 in the weeks four weeks
before a federal voting Sunday. Every call is in the AI call log under the purposes
`politics_*` (plus `article_translate` and `article_translation_review`).

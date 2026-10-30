# Content pipeline: drafting, checking and translating questions

The question bank is the YAML files under `content/` (D-041, `content/README.md`). The scripts
under `scripts/content/` draft and check them with the AI provider; a person approves every
question in the admin area. Every AI call goes through `app/llm/` and is written to the AI call
log (Admin, Usage) with its cost. The scripts change files only; commit the files afterwards in
a normal pull request, and the import on deploy fills the database.

Prerequisites: a working `.env` with `ANTHROPIC_API_KEY` (the staging key), `DATABASE_URL`
pointing at a migrated database (the cost log and the review write-back live there; locally
`alembic upgrade head` on SQLite is enough) and the repository installed (`pip install -e
".[dev]"`). Never run the scripts against production data without Chris.

## Order of commands for one topic

```bash
# 0. Where do we stand? Counts per status and language, and each topic's gap to its target.
python -m scripts.content.stats --canton zh

# 1. Draft in German. Default count: target_questions minus the questions on the topic that
#    are not retired. Near-duplicates of existing questions are skipped and listed.
python -m scripts.content.draft --canton zh --topic bund.demokratie.volksrechte

# 2. Independent answer without the key. Disagreement -> status needs_fix.
python -m scripts.content.answer --canton zh --topic bund.demokratie.volksrechte

# 3. Source check against the cited page. not_supported or a dead link -> needs_fix;
#    supported refreshes sources[].checked.
python -m scripts.content.source_check --canton zh --topic bund.demokratie.volksrechte

# 4. Drafts with an agreeing answer and a supported source -> in_review.
python -m scripts.content.promote --canton zh --topic bund.demokratie.volksrechte

# 5. Commit and deploy; a person reviews in Admin, Question bank (approve, send back, retire).
# 6. Write the review actions back to the files, then commit and deploy again.
python -m scripts.content.sync_reviews

# 7. Translate the approved questions, then check each translation by back-translation.
python -m scripts.content.translate --lang all --canton zh --topic bund.demokratie.volksrechte
python -m scripts.content.back_translate --lang all

# 8. Validate before committing (CI runs the same check).
python scripts/validate_content.py
```

Every script prints what it did per question. `--ids a b c` limits a step to some questions,
`--redo` repeats a check that already ran for the current version, `--today` is for tests.
`promote` and `sync_reviews` have `--dry-run`.

Statuses: `draft` (new or waiting for checks), `needs_fix` (a check or a reviewer found a
problem; the reason is under `checks` or `review.note`; never served), `in_review` (all checks
passed, waiting for a person), `approved`, `retired`. Translations: `draft`, `flagged` (the
back-translation means something else; never served), `in_review`, `approved`.

## Batch or direct

The batch API is the default: half the list price, results usually within an hour and always
within 24 hours. The script sends one batch, prints its id, waits (checking every 30 seconds,
`--poll-seconds`) and writes the results. If the run is interrupted (laptop closed, network
gone), the batch still finishes and is still billed: repeat the same command with
`--resume <batch id>` to collect it instead of paying twice. The request map of every batch is
kept in `var/content-batches/<batch id>.json`. `back_translate` sends two batches one after the
other; resume them with `--resume <first>` and, if the second was sent, `--resume-compare
<second>`.

`--direct` sends the requests one by one at the full price and returns in seconds. Use it for a
handful of questions, for a single `--ids` re-check, or while trying out a new prompt version.

Other limits: `--max-requests` (default 500) refuses larger runs, and nothing starts once this
month's AI spend has reached `AI_MONTHLY_BUDGET_CHF` (override with `--allow-over-budget`). The
model is `TUTOR_MODEL` unless `--model` says otherwise.

## Expected cost per 50 questions

Estimated from `app/llm/pricing.py` (Sonnet 5.5: USD 2 per million input tokens, USD 10 per
million output tokens; batch at half price) and typical request sizes. The AI call log shows the
real figures; update this table after the first topic.

| Step | Requests | Tokens in / out per request | List price (USD) | Batch (USD) |
| --- | --- | --- | --- | --- |
| Draft (5 questions per request) | 10 | 2,500 / 2,500 | 0.30 | 0.15 |
| Independent answer | 50 | 700 / 80 | 0.11 | 0.06 |
| Source check (page excerpts up to 12,000 characters each) | 50 | 6,000 / 120 | 0.66 | 0.33 |
| **German total** | | | **1.07** | **0.54** |
| Translation, per language | 50 | 1,300 / 450 | 0.36 | 0.18 |
| Back-translation and comparison, per language | 100 | 900 / 450 and 1,300 / 60 | 0.48 | 0.24 |
| **Seven languages** | | | **5.88** | **2.94** |
| **All steps** | | | **about 7** | **about 3.50** |

So about CHF 3 per 50 questions with the batch API (CHF 5.50 direct) at `USD_CHF_RATE` 0.80, plus
perhaps 20% for redrafts and re-checks. The whole Zurich bank (about 350 questions) in German
and seven languages comes to about CHF 20 to 25 with batches. Opus 5.5 would double these
figures; Haiku 5.5 costs a twentieth but is not recommended for drafting or the source check.

## What needs a person

- **Approval.** Only a person approves a question (Admin, Question bank). `promote` only
  moves fully checked drafts to `in_review`.
- **`needs_fix` questions.** Read `checks.independent_answer.reasoning`, `checks.source.note`
  or `review.note` in the file. Either fix the file (raise `version`, set `status: draft`, run
  the checks again) or, when the check was wrong, approve it in the admin area anyway; the
  reviewer may overrule a check.
- **`unclear` source checks.** Pages that need JavaScript (fedlex.admin.ch renders the
  constitution with JavaScript) or PDFs give no readable text, so the check says `unclear` and
  the draft stays a draft. Either cite an additional ch.ch or admin.ch page and re-run
  `source_check --ids ...`, or check the page by hand and record it in the file:
  `checks.source: {verdict: supported, note: "checked by hand: Art. 138 BV", at: <date>,
  version: <version>}` with `sources[].checked` set to that date.
- **Translations.** A native-speaker reviewer checks the first 100 questions of each language
  in full, then a 10% sample of each batch plus every `flagged` translation, and sets
  `status: approved` with `reviewed_by` and `reviewed_at`. The pipeline never overwrites a
  translation that is `approved` or `in_review`; to have one refreshed after the German
  changed, set it back to `draft` by hand.
- **Glossary.** The entries in `content/glossary/<lang>.yaml` whose `source` says "to confirm"
  or "draft for native-speaker review" need checking: French, Italian and English institution
  names against TERMDAT (https://www.termdat.bk.admin.ch), the other languages by the
  reviewer. Fix the file; the next translation run uses it.
- **Never copy catalogue text.** The draft prompt forbids it, but a reviewer who recognises a
  question from a cantonal catalogue or test series sends it back.

## Yearly re-check and weekly link check

- Every year (Zurich updates its catalogue each year), and at the latest before any source
  passes 365 days: `python -m scripts.content.recheck_sources --older-than 300`. Same rules as
  the source check: supported refreshes the date, not_supported or a dead link sets the
  question to `needs_fix` and takes it out of the app at the next deploy.
- The worker job `check_source_links` runs every Monday at 04:30 UTC (HEAD or GET, no AI). A
  question with a broken link gets `file_sync_pending` in the database, and the report is
  written to `content/reports/link-check-<date>.md` (on the server, where `content/` is
  read-only, to `var/reports/`). The question stays served. Run `sync_reviews` to record the
  broken links in the files, fix or replace the sources, then `source_check --ids ...`. The
  same check runs locally with `python -m scripts.content.check_links` (`--no-db` for the
  report only).

## Recovering from a bad batch

The scripts only write files, so a bad run is undone in git:

1. `git status content/` shows what the run wrote. Drafts are new files with `status: draft`
   and `version: 1`; checks changed existing files.
2. Throw the run away: `git restore content/` for changed files and `git clean -n content/`
   then `git clean -f content/questions content/translations` for new ones (or delete the new
   draft files by hand). Nothing in the database needs undoing: drafts reach the database only
   after a commit and a deploy, and the cost log rows stay (the money was spent).
3. Fix the cause (prompt, topic sources, model, `--per-request`), and if the prompt changed,
   add a new version `prompts/content/<step>/v2.md` rather than editing v1, so the call log
   tells the runs apart.
4. Run the step again. A batch with many `errored` results (shown as "gave no usable reply")
   can simply be re-run; items that succeeded are not sent again because their check is
   already recorded for the current version.

If drafts were already committed and deployed, set the bad ones to `status: retired` (never
delete a question that has been live) or, if they were never approved, delete the files; the
import retires questions whose files are gone.

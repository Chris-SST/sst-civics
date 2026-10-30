# Content files

The question bank lives here as versioned YAML files: the repository is the master copy and the
database is filled from it on every deploy (D-041). The Pydantic models that check these files
are in `app/content/schema.py`; keep the two in step.

```
content/
  topics/<canton>.yaml                 topic list of a canton (zh.yaml, later ag.yaml)
  questions/<scope>/<id>.yaml          one file per question; scope federal, zh, ag or zh-<commune>
  translations/<lang>/<id>.yaml        one file per question and language (en fr it pt es sq tr)
  glossary/<lang>.yaml                 key German terms with translations (optional, task 1.3)
```

Never copy text from a cantonal question catalogue or test series into these files. The
catalogues may be used only to list topics. Every question is written in our own words.

## Topics: `topics/<canton>.yaml`

```yaml
canton: zh                       # file name and canton code agree
test:                            # optional; read by the mock test (task 1.9)
  questions: 50
  minutes: 60
  pass_mark: 30                  # optional
  proportions: {federal: 0.78, canton: 0.16, commune: 0.06}
topics:
  - code: bund.demokratie.volksrechte     # dotted, lower case, stable; never rename
    scope: federal                        # federal | canton | commune
    name_de: "Volksrechte: Initiative, Referendum und Abstimmungen"
    name_en: "Popular rights: initiative, referendum and votes"
    target_questions: 22
    sources: [https://www.ch.ch/de/]      # https only
```

- Codes start with `bund.` (federal), `kanton.` (canton) or `gemeinde.` (commune), match
  `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` and are unique within the file. The order of the file
  is the order learners see (the catalogue's order).
- Federal topics appear in every canton's file with the same code and names; federal questions
  may use a federal topic from any canton file. Mastery is kept per learner and topic code, so
  progress on federal topics carries over between cantons.

## Questions: `questions/<scope>/<id>.yaml`

```yaml
id: bundesrat-mitglieder          # stable slug: a-z, 0-9 and hyphens; the file name is <id>.yaml
version: 1                        # whole number; rises by one on every change to this file
scope: federal                    # federal | zh | ag | zh-<commune>; the folder is the scope
canton: null                      # null for federal, otherwise the canton code (zh-x -> zh)
topic: bund.demokratie.bundesrat  # a code from topics/<canton>.yaml
question_de: "..."
options_de:                       # exactly four, keyed a to d, all different
  a: "..."
  b: "..."
  c: "..."
  d: "..."
correct: b                        # a, b, c or d
explanation_de: >-                # two or three sentences
  ...
sources:                          # at least one; one must be checked within the last 365 days
  - url: https://www.admin.ch/...
    checked: 2026-10-30
glossary: [Bundesrat]             # key German terms in the question
status: draft                     # draft | in_review | approved | retired
difficulty: 2                     # 1, 2 or 3
translations_missing: false       # optional; true lets an approved question lack translations
```

- A federal question uses a federal topic; a canton question (`zh`) a canton or commune topic of
  that canton; a commune question (`zh-winterthur`) a commune topic.
- Learners see approved questions (on staging also `in_review`, see `SERVE_UNREVIEWED_QUESTIONS`),
  federal plus their canton's. Commune questions (`zh-<commune>`) are not served until the app
  knows a learner's commune (Phase 2).
- Never delete a question that has been live; set `status: retired`. A question whose file is
  removed is retired on the next import, never deleted, so learners' answers stay.

## Translations: `translations/<lang>/<id>.yaml`

```yaml
id: bundesrat-mitglieder
lang: en                          # en fr it pt es sq tr; the folder is the language
source_version: 1                 # the German version this translates
question: "..."
options: {a: "...", b: "...", c: "...", d: "..."}
explanation: "..."
status: draft                     # draft | in_review | approved
reviewed_by: null                 # required (with reviewed_at) when approved
reviewed_at: null                 # ISO date
```

- Translate only approved German questions. An approved question needs a translation file for
  every launch language, or `translations_missing: true` until they exist.
- When the German `version` rises, every translation with a lower `source_version` is stale: the
  check reports it as a warning, the import keeps it but marks it hidden, and the app does not
  show it until it is refreshed and its `source_version` raised.
- The pipeline (task 1.5) never overwrites a translation a reviewer approved.

## Glossary: `glossary/<lang>.yaml`

```yaml
lang: en
terms:
  - term: Ständerat
    translation: Council of States
    note: "The chamber of the cantons; ..."
```

## Checking and importing

```bash
python scripts/validate_content.py        # in CI before the tests; exits 1 on any error
python -m scripts.import_content          # on deploy, after alembic upgrade head
```

The check reports errors (shape, four different options, a correct key, a source checked in the
last 365 days, a known topic, an explanation, unique ids, translations for approved questions)
and warnings (stale translations, translations of questions not yet approved), then prints a
summary per scope and language.

The import validates first and writes nothing if there is any error. It matches questions on
`id`: a higher `version` replaces the row; the same version with the same content is left
alone; the same version with different content is an error (raise the version), and the whole
import is rolled back.

## Admin review and these files

The admin review queue (Admin, Question bank) can approve a question (optionally with edits),
send it back to draft with a note, or retire it. **These actions are recorded in the database
only; they are not written back to these files yet.** Each one sets `file_sync_pending` on the
question and is listed in its `pending_changes`, with the reviewer, time, note and edits; the
same actions are in the audit log. The file must then be updated by the pipeline (task 1.5 adds
the write-back), with the version raised.

Until then the next import keeps the admin's status as long as the file's version has not
changed. Once a new version of the file is imported, the file wins and the pending changes are
cleared (the import names each question where that happened).

## Examples

The example questions used by the tests (`beispiel-*`) are in `tests/fixtures/content/`, not
here, so they never reach the question bank.

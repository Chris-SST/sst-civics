# Prompts

Versioned files only; no prompt text lives in code. The highest `vN` in each directory is
active, and the version string is written to every row of the AI call log.

| Path | Purpose |
| --- | --- |
| `base/vN.md` | Persona, teaching method, scope, wellbeing and safety rules, language and formatting. Each shared rule is stated here once (the learner's own case, what to do when unsure, no filler and no disclaimers); the other prompts do not repeat it. Placeholders `{{TUTOR_NAME}}` and `{{PROVIDER_DISCLOSURE}}` are filled from settings. |
| `civics/vN.md` | Civics-trainer context sent after the base instructions and cached with them: what the knowledge test is, the three levels of government and direct democracy. The learner's canton and topic follow in the per-session context. |
| `help/vN.md` | Help chat rules (D-066): answer from the reference material that follows it (`content/help/`, built by `scripts/build_help_pack.py`), say when it does not cover a question, link one guide page, point to the residence calculator for the learner's own case. |
| `gatekeeper/vN.md` | Instructions for the fast model that labels each learner message (on topic, borderline, off topic, override, wellbeing). Version 2 is the civics wording: on topic means about the question under discussion or its topic; the learner's own application is borderline. |
| `explain/vN.md` | "Explain this": the block added to the learner context of a conversation bound to one question: the question, options, correct key, explanation, approved translation and sources (placeholders `{{QUESTION_DE}}`, `{{OPTIONS_DE}}`, `{{CORRECT}}`, `{{EXPLANATION_DE}}`, `{{TRANSLATION}}`, `{{SOURCES}}` filled per question), and the rules: reply language, stay on the question, a few sentences, refer to the listed sources. |
| `summary/vN.md` | Instructions for the running summary of older turns. |
| `replies/vN.json` | Fixed server replies in en/de/fr: off topic, override, session ended, refusal, error. |
| `content/draft/vN.md` | Content pipeline: drafting four-option questions in Swiss standard German (`scripts/content/draft`). |
| `content/answer/vN.md` | Independent answer without the key (`scripts/content/answer`). |
| `content/source_check/vN.md` | Does the cited page support the answer (`scripts/content/source_check`, `recheck_sources`). |
| `content/translate/vN.md` | Translation of approved questions with the glossary (`scripts/content/translate`). |
| `content/back_translate/vN.md` | Independent translation back into German (`scripts/content/back_translate`). |
| `content/compare/vN.md` | Original against back-translation: same or different (`scripts/content/back_translate`). |
| `articles/write/vN.md` | Article pipeline (D-073): writes one article or canton guide from the plan and the sources read (`app/articles/produce.py`). |
| `articles/review/vN.md` | Independent fact review of the English article against the same sources. |
| `articles/fix/vN.md` | Revision after review findings or Chris's suggested changes. |
| `articles/translate/vN.md` | Translation into one site language with the glossary, placeholders untouched. |
| `articles/translation_review/vN.md` | Independent review of one translation against the English. |
| `politics/write_roundup/vN.md`, `write_vote`, `write_whoswho` | Politics in your canton (D-074, `app/politics/produce.py`): writing a weekly round-up, a vote explainer, the who's who from the authorities' pages. |
| `politics/neutrality_review/vN.md` | Independent neutrality review; a blocker stops publication. |
| `politics/fact_review/vN.md` | Independent fact review of a politics page against the same pages. |
| `politics/fix/vN.md` | Revision after a format check, the neutrality or the fact review. |
| `politics/select/vN.md` | Picks the political items of the week from the item pages fetched. |
| `politics/links/vN.md`, `proposals`, `results`, `roster` | Cheap extraction calls: links of a listing that did not parse, the proposals of a vote announcement, result figures stated on a page, the who's-who facts. |
| `politics/questions/vN.md`, `question_check`, `question_translate` | Current-affairs practice questions: writing in German, the independent check without the key, the translations. |
Politics pages are translated with `articles/translate` and `articles/translation_review`.

The tutor's prompt version is logged as `base@vN+civics@vN`, with `+explain@vN` in "Explain this" and `+help@vN` in the help chat. The school course modules
(`courses/<module>/`) and the course-based question prompts (`questions/generate`,
`questions/solve`) were removed in Phase 1 task 1.1 with the course concept; they are in git
history. The content pipeline's prompts are under `content/` (task 1.5, logged as `content/<step>@vN`;
see docs/runbooks/content-pipeline.md); "Explain this" is `explain/` (task 1.10).

Any change bumps the version and runs the evaluation suite in `evals/`.

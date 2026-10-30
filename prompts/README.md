# Prompts

Versioned files only; no prompt text lives in code. The highest `vN` in each directory is
active, and the version string is written to every row of the AI call log.

| Path | Purpose |
| --- | --- |
| `base/vN.md` | Persona, teaching method, scope, wellbeing and safety rules, language and formatting. Placeholders `{{TUTOR_NAME}}` and `{{PROVIDER_DISCLOSURE}}` are filled from settings. |
| `civics/vN.md` | Civics-trainer context sent after the base instructions and cached with them: what the knowledge test is, the three levels of government, how to handle facts and limits. The learner's canton and topic follow in the per-session context. |
| `gatekeeper/vN.md` | Instructions for the fast model that labels each learner message (on topic, borderline, off topic, override, wellbeing). Version 2 is the civics wording: on topic means about the question under discussion or its topic; the learner's own application is borderline. |
| `explain/vN.md` | "Explain this": the block added to the learner context of a conversation bound to one question: the question, options, correct key, explanation, approved translation and sources (placeholders `{{QUESTION_DE}}`, `{{OPTIONS_DE}}`, `{{CORRECT}}`, `{{EXPLANATION_DE}}`, `{{TRANSLATION}}`, `{{SOURCES}}` filled per question), and the rules: reply language, stay on the question, a few sentences, no legal advice about the learner's own application, refer to the sources. |
| `summary/vN.md` | Instructions for the running summary of older turns. |
| `replies/vN.json` | Fixed server replies in en/de/fr: off topic, override, session ended, refusal, error. |
| `content/draft/vN.md` | Content pipeline: drafting four-option questions in Swiss standard German (`scripts/content/draft`). |
| `content/answer/vN.md` | Independent answer without the key (`scripts/content/answer`). |
| `content/source_check/vN.md` | Does the cited page support the answer (`scripts/content/source_check`, `recheck_sources`). |
| `content/translate/vN.md` | Translation of approved questions with the glossary (`scripts/content/translate`). |
| `content/back_translate/vN.md` | Independent translation back into German (`scripts/content/back_translate`). |
| `content/compare/vN.md` | Original against back-translation: same or different (`scripts/content/back_translate`). |

The tutor's prompt version is logged as `base@vN+civics@vN`, with `+explain@vN` in "Explain this". The school course modules
(`courses/<module>/`) and the course-based question prompts (`questions/generate`,
`questions/solve`) were removed in Phase 1 task 1.1 with the course concept; they are in git
history. The content pipeline's prompts are under `content/` (task 1.5, logged as `content/<step>@vN`;
see docs/runbooks/content-pipeline.md); "Explain this" is `explain/` (task 1.10).

Any change bumps the version and runs the evaluation suite in `evals/`.

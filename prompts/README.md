# Prompts and course modules

Versioned files only; no prompt text lives in code. The highest `vN` in each directory is
active, and the version string is written to every row of the AI call log.

| Path | Purpose |
| --- | --- |
| `base/vN.md` | Persona, teaching method, scope, wellbeing and safety rules, language and formatting. Placeholders `{{TUTOR_NAME}}` and `{{PROVIDER_DISCLOSURE}}` are filled from settings. |
| `courses/<module>/vN.md` | Course module: course shape, topic codes, command terms, notation, calculator rules, misconceptions, SL/HL differences. Draft until an SST tutor approves it. Topic names and codes only; never syllabus text, past papers or mark schemes. |
| `courses/<module>/topics.json` | Course and level names in en/de/fr and the topic list students pick from (`levels` restricts a topic to SL or HL). |
| `gatekeeper/vN.md` | Instructions for the fast model that labels each student message (on topic, borderline, off topic, override, wellbeing). |
| `summary/vN.md` | Instructions for the running summary of older turns. |
| `replies/vN.json` | Fixed server replies in en/de/fr: off topic, override, session ended, refusal, error. |

Course modules exist for `ib_maths_aa`, `ib_maths_ai` and `ib_physics`; the student's course
key (`ib_maths_aa_hl`) maps to the module by dropping the level, which travels as context.

Any change bumps the version and runs the evaluation suite in `evals/`.

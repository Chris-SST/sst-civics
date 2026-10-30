# Interface locales

One JSON file per interface language. `en-GB.json` is the source; every other file must have
exactly the same keys. Check with `npm run check:locales` (run from `web/`). The check also fails
if a `{{placeholder}}` differs from the English string.

None of the existing files carries a metadata key, so status is recorded here rather than in the
JSON.

| File | Language | Status |
| --- | --- | --- |
| `en-GB.json` | English (British) | Source text |
| `de-CH.json` | German (Swiss, formal) | Original translation |
| `fr-CH.json` | French (Swiss) | Original translation |
| `it-CH.json` | Italian (Ticino conventions, "Lei") | Machine draft, awaiting native-speaker review, 30 October 2026 |
| `pt-PT.json` | Portuguese (Portugal, formal) | Machine draft, awaiting native-speaker review, 30 October 2026 |
| `es-ES.json` | Spanish ("usted") | Machine draft, awaiting native-speaker review, 30 October 2026 |
| `sq-AL.json` | Albanian ("ju") | Machine draft, awaiting native-speaker review, 30 October 2026 |
| `tr-TR.json` | Turkish ("siz") | Machine draft, awaiting native-speaker review, 30 October 2026 |

## Review rule

Under the plan, a native reviewer must check the first 100 strings of each machine-drafted
language (in file order) before that language is shown to learners as finished. Record the
reviewer and date here when done, and change the status of the file.

## Adding or changing strings

Edit `en-GB.json` first, then add the key to every other file and run the check. Keep
placeholders, HTML and Markdown exactly as in English. Amounts stay in CHF; product names are not
translated.

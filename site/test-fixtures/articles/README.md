# Article fixtures

A small, clearly fake set of articles for the build tests (`ARTICLES_DIR=test-fixtures/articles npm run build`).
The facts in them are invented. They are never published; the live site reads the real files from the
server volume. They exercise every front-matter field and every link placeholder:

- `fixture-spouse` (article, en + de, different slugs, German marked `machine_translated`)
- `fixture-test-prep` (article, en + de): links to `article:` (published and English-only targets), `guide:` and `try:`
- `fixture-canton-ag` (canton guide, English only)

Politics pages (docs/politics-contract.md), all canton `zh`:

- `fixture-zh-week-46` (round-up, en + de), `fixture-zh-week-34` (old round-up, en: tests the staleness note)
- `fixture-vote-zh-2026-09-27` (past vote with a result box, en), `fixture-vote-zh-2027-03-07` (coming vote, en)
- `fixture-zh-whos-who` (who's who, en)

The README is not an article: only `<lang>/<slug>.md` files are read.

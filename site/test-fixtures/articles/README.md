# Article fixtures

A small, clearly fake set of articles for the build tests (`ARTICLES_DIR=test-fixtures/articles npm run build`).
The facts in them are invented. They are never published; the live site reads the real files from the
server volume. They exercise every front-matter field and every link placeholder:

- `fixture-spouse` (article, en + de, different slugs, German marked `machine_translated`)
- `fixture-test-prep` (article, en + de): links to `article:` (published and English-only targets), `guide:` and `try:`
- `fixture-canton-ag` (canton guide, English only)

The README is not an article: only `<lang>/<slug>.md` files are read.

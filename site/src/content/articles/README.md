# Articles (local checkout)

This folder is where the site looks for article files when `ARTICLES_DIR` is not set. Everything here is
git-ignored except this README. On the server the files live in the `articles` volume instead.

Layout: `<lang>/<slug>.md`, with the front matter and body rules in `docs/articles-contract.md`. For a local
preview, build with `ARTICLES_DIR=test-fixtures/articles npm run build`. Without any files the site builds
fine: the article index says the first articles are coming soon.

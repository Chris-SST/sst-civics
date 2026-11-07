# Article topic queue

`plan.yaml` is the topic queue for the automated article pipeline: 12 articles (Mondays, 16 Nov 2026 to 1 Feb 2027) and 5 canton guides (Thursdays, 19 Nov 2026 to 21 Jan 2027), each at 07:00 Zurich time. The format is section 5 of `docs/articles-contract.md`.

- Each entry has a brief (audience, question, angle, what the existing guide pages already cover and must not be repeated), an outline, `must_cover` facts and seed `sources`.
- Every `must_cover` fact ends with the source that supports it in square brackets. All source URLs were fetched as plain text (no JavaScript) on 7 November 2026 and contained the facts attributed to them. Federal law uses the Fedlex filestore (HTML, or PDF for the Ordinance), not fedlex.admin.ch or ch.ch.
- Cantonal and commune figures (fees, test formats) carry the date of the document in the brief; the pipeline must state the date it checked them.
- `dual-citizenship` lists 12 sources (the SEM plus official pages for nine countries), above the usual 3-8, because each country needs its own official page.
- Do not add cantonal question catalogues or test series as sources (project rule).

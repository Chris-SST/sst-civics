"""Politics in your canton (D-074, docs/politics-contract.md; runbook
docs/runbooks/politics.md).

The pages are rows of `articles` with kind roundup, vote or whoswho, and share the article
pipeline's translations, files, build requests and live check (app/articles/). What is
different lives here:

- `sources`: content/politics/sources.yaml, one block per canton.
- `discover`: reading listings, feeds and vote lists (deterministic parsers, a cheap model
  call only when a listing does not parse), the item store, vote and result discovery.
- `produce`: research, selection, writing, the neutrality review, the fact review, fixes and
  translations of one page.
- `schedule`: the 15-minute tick: Friday round-ups, vote explainers four weeks ahead and
  their results, the monthly who's who, publication without a proposal email.
- `questions`: the expiring current-affairs practice questions, and what the app serves.
- `routes`: the app's "Current affairs" endpoints. `report`: the digest section.
"""

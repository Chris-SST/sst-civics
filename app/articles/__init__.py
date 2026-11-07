"""Automated article pipeline (D-073). The interface with the site and the site builder is
docs/articles-contract.md; the runbook is docs/runbooks/articles.md.

Modules: `constants` (languages, URL segments, guide keys), `plan` (plan.yaml import),
`research` (seed sources), `produce` (writing, fact review, fixes, translations),
`validate` (deterministic checks), `files` (Markdown files and build requests), `workflow`
(states, timing, the tick, proposals, publication), `emails`, `routes` (Chris's review page),
`tokens` (signed review links), `render` (Markdown to HTML for emails and the page),
`report` (the digest section) and `dryrun` (placeholder content without AI)."""

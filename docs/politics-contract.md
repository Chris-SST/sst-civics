# Politics in your canton: contract (D-074)

Chris approved this on 7 November 2026 ("Ok for all"). It extends `docs/articles-contract.md`, and everything there applies unless this file says otherwise.

- **Scope:** canton of Zurich only for now, but everything is keyed by canton so others can be added later.
- **Review:** no proposal email. Pages publish automatically once they pass the reviews, and they appear in the daily digest.
- **App:** each round-up and vote explainer also produces a few current-affairs practice questions for the app, which expire.

## Kinds

| kind | key pattern | What it is | Schedule |
|---|---|---|---|
| `roundup` | `zh-week-2026-46` (ISO week) | 4-6 political items of the past week: decisions of the cantonal government (Regierungsrat) and parliament (Kantonsrat), new laws, initiatives, coming votes; plus the city of Zurich and Winterthur where relevant | Every Friday at 07:00 Zurich time, covering Friday to Thursday |
| `vote` | `vote-zh-2027-03-07-<slug>` or `vote-ch-<date>-<slug>` | One cantonal or federal proposal: what changes, the arguments of each side, the result once known | Discovered from the official vote pages. Published about 4 weeks before the vote date; the result is added after the vote |
| `whoswho` | `zh-whos-who` | Members of the cantonal government and their departments, the parties in the Kantonsrat with their seats, and the mayor and executive of Zurich and Winterthur | Checked on the 1st of each month. Republished only if something changed |

## Files

- Same directory, `ARTICLES_DIR/<lang>/<slug>.md`, and the same frontmatter as the articles, with these differences:
  - `category: politics` (new enum value)
  - `kind`: `roundup`, `vote` or `whoswho`
  - `canton` is required (`zh`; a federal vote uses `ch`)
  - `roundup` adds `period_start` and `period_end` (dates)
  - `vote` adds `vote_date` (date) and `vote_level` (`cantonal` | `federal`), and optionally `result`: `{yes_percent, turnout_percent, accepted}`, filled in after the vote
  - `faq` is optional here (0-5)
  - `summary` has 3-6 items
  - `sources` has 1-20 items
  - `related` may also hold article keys
- **Body:**
  - A `roundup` has one `##` per item. Each item ends with a "Source:" line linking its official page.
  - A `vote` has the sections "What it is about", "What would change", "Arguments in favour", "Arguments against", "Who recommends what" and, after the vote, "Result".
  - Word ranges: roundup 500-1,100, vote 600-1,200, whoswho 300-1,000.

## URLs

| | en | de | fr | it | pt | es | sq | tr |
|---|---|---|---|---|---|---|---|---|
| segment | politics | politik | politique | politica | politica | politica | politika | siyaset |

- Page: `/<lang>/<segment>/<canton>/<slug>/`, for example `/en/politics/zh/canton-of-zurich-week-46-2026/`.
- Index per canton: `/<lang>/<segment>/<canton>/`. It shows the who's-who first, then coming votes, then the round-ups, newest first, with a dated archive.
- Overview: `/<lang>/<segment>/`, listing the cantons covered.
- Every page shows its date prominently, and a round-up older than 8 weeks shows "This round-up is from <date>. The latest is here" with a link.
- RSS: the articles feed also includes politics pages.

## Rules for the content

- **Neutrality comes first.** No party, side or person is favoured, and there is no recommendation on how to vote. Arguments come only from each side's own statements: the government or parliament majority, the committee behind the initiative or referendum, and the parties' published recommendations. Both sides get comparable length. Loaded words are avoided.
- **Sources:**
  - Only the authorities' own pages: zh.ch (including the Kantonsrat at kantonsrat.zh.ch), stadt-zuerich.ch, stadt.winterthur.ch, admin.ch (including bk.admin.ch and the federal voting booklet) and parlament.ch.
  - No newspapers or party websites, except a party's own voting recommendation if no official page lists it.
  - Summaries are in our own words, never copied.
- **No personal data beyond public office-holders** (name, office, party), and nothing about private individuals.
- Plain British English for people preparing for the naturalisation interview. Each round-up ends with a short line saying that your own commune's news is the best place for local matters.

## Pipeline

1. **Discovery** (`content/politics/sources.yaml`, in git, one block per canton): listing pages and feeds to read, each with a type.
2. **Selection:** a model call picks the political items of the period from the item pages actually fetched.
3. **Writing:** Opus.
4. **Neutrality review:** an independent Opus call. A blocker stops publication.
5. **Fact review:** an independent Opus call, as for the articles.
6. **Translations with review:** as for the articles.
7. **Publication:** immediately, through the same build request and live check, with no proposal email. Failures become `needs_attention` and show in the digest and in one email.

## Practice questions in the app

- From each published round-up and vote explainer: 2-3 multiple-choice questions on facts stated in the page.
- They are stored as a separate set (`current_affairs`, canton `zh`) with `expires_at` (round-up +6 months, vote +12 months). They go through an independent check before they are served.
- They are shown in the app as an optional "Current affairs (canton of Zurich)" topic. They are never part of the mock test, the official catalogue topics or readiness figures.
- Every question shows the date it refers to and links to the guide page.

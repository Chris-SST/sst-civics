"""Fixed values of the article contract (docs/articles-contract.md, sections 1 and 2)."""

from __future__ import annotations

import re

LANGS = ("de", "en", "fr", "it", "pt", "es", "sq", "tr")
TRANSLATION_LANGS = tuple(lang for lang in LANGS if lang != "en")
KINDS = ("article", "canton")  # the planned articles of content/articles/plan.yaml
CATEGORIES = ("eligibility", "cantons", "test", "process", "after")
# "Politics in your canton" (docs/politics-contract.md, D-074): pages the worker finds and
# writes itself, published without a proposal email. Same table, files and builder.
POLITICS_KINDS = ("roundup", "vote", "whoswho")
POLITICS_CATEGORY = "politics"
ALL_KINDS = KINDS + POLITICS_KINDS

# URL segment per kind and language: /<lang>/<segment>/<slug>/
SEGMENTS: dict[str, dict[str, str]] = {
    "article": {
        "en": "articles",
        "de": "ratgeber",
        "fr": "articles",
        "it": "articoli",
        "pt": "artigos",
        "es": "articulos",
        "sq": "artikuj",
        "tr": "makaleler",
    },
    "canton": {
        "en": "cantons",
        "de": "kantone",
        "fr": "cantons",
        "it": "cantoni",
        "pt": "cantoes",
        "es": "cantones",
        "sq": "kantonet",
        "tr": "kantonlar",
    },
}

_POLITICS_SEGMENT = {
    "en": "politics",
    "de": "politik",
    "fr": "politique",
    "it": "politica",
    "pt": "politica",
    "es": "politica",
    "sq": "politika",
    "tr": "siyaset",
}
for _kind in POLITICS_KINDS:  # /<lang>/<segment>/<canton>/<slug>/
    SEGMENTS[_kind] = _POLITICS_SEGMENT

# The keys of SLUGS in site/src/i18n/pages.mjs (the worker image has no site/ folder, so the
# list is kept here; tests/test_articles_validate.py fails when the two differ).
GUIDE_KEYS = (
    "overview",
    "zurich",
    "documents",
    "test",
    "language",
    "fees",
    "interview",
    "topicDemocracy",
    "topicSocial",
    "topicHistory",
    "topicGeography",
    "topicCulture",
    "topicZurich",
    "calculator",
    "free",
    "faq",
    "glossary",
    "eligibility",
    "checklist",
    "articles",
    "cantons",
    "politics",
    "imprint",
    "contact",
    "about",
    "terms",
    "privacy",
)

# Cantons a canton guide may be about (lower case; "ch" is not a canton).
CANTON_CODES = (
    "ag", "ai", "ar", "be", "bl", "bs", "fr", "ge", "gl", "gr", "ju", "lu", "ne",
    "nw", "ow", "sg", "sh", "so", "sz", "tg", "ti", "ur", "vd", "vs", "zg", "zh",
)  # fmt: skip

KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_RE = KEY_RE
SLUG_MAX = 80
TITLE_MAX = 90
DESCRIPTION_MIN, DESCRIPTION_MAX = 70, 160
SUMMARY_MIN, SUMMARY_MAX = 3, 5
FAQ_MIN, FAQ_MAX = 3, 5
SOURCES_MIN, SOURCES_MAX = 2, 12
RELATED_MAX = 4
# Word counts of the English body. The contract says "about 900-1,300" (articles) and
# "1,200-1,800" (canton guides); the check allows some slack on both sides.
WORDS = {"article": (800, 1450), "canton": (1100, 2000)}
# Politics (contract: roundup 500-1,100, vote 600-1,200, whoswho 300-1,000), with slack.
WORDS.update({"roundup": (450, 1200), "vote": (550, 1300), "whoswho": (280, 1100)})
# Lengths that differ for the politics kinds (contract "Files").
POLITICS_SUMMARY = (3, 6)
POLITICS_FAQ = (0, 5)
POLITICS_SOURCES = (1, 20)
# Hosts a politics page may cite (contract "Sources"); a subdomain counts. The Kantonsrat's
# document server is added because its session bulletins are linked from kantonsrat.zh.ch
# (content/politics/sources.yaml).
POLITICS_SOURCE_HOSTS = (
    "zh.ch",
    "stadt-zuerich.ch",
    "stadt.winterthur.ch",
    "admin.ch",
    "parlament.ch",
    "parlzhcdws.cmicloud.ch",
)
VOTE_LEVELS = ("cantonal", "federal")
# Sections of a vote explainer, in this order; "Result" only after the vote.
VOTE_SECTIONS = (
    "What it is about",
    "What would change",
    "Arguments in favour",
    "Arguments against",
    "Who recommends what",
)
VOTE_RESULT_SECTION = "Result"
ROUNDUP_ITEMS = (4, 6)  # contract: 4-6 items; a week with fewer is skipped (D-074)

# IndexNow (contract section 4): key file /<key>.txt on the guide site.
INDEXNOW_KEY = "db4ff15a4e2f78e09e2d5d2021e47cd3"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

# The review page stays usable this long after a publication, for corrections.
UPDATE_WINDOW_DAYS = 14

LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "es": "Spanish",
    "sq": "Albanian",
    "tr": "Turkish",
}

# What each guide page is about, for the writer's internal links (guide:<key>).
GUIDE_PAGE_TOPICS = {
    "overview": "How naturalisation works: federal requirements, the three levels, the steps",
    "zurich": "The canton of Zurich step by step",
    "documents": "Documents for an application in Zurich",
    "test": "The knowledge test (Zurich format, how to prepare)",
    "language": "Language certificates: B1 spoken, A2 written, accepted certificates",
    "fees": "Fees in Zurich",
    "interview": "The naturalisation interview",
    "topicDemocracy": "Knowledge test topic: democracy and federalism",
    "topicSocial": "Knowledge test topic: the welfare state",
    "topicHistory": "Knowledge test topic: history",
    "topicGeography": "Knowledge test topic: geography",
    "topicCulture": "Knowledge test topic: culture and society",
    "topicZurich": "Knowledge test topic: canton and commune of Zurich",
    "calculator": "Residence-years calculator (runs in the browser)",
    "free": "Free practice questions",
    "faq": "Frequently asked questions",
    "glossary": "Glossary of the German administrative words",
    "eligibility": "Eligibility check: which route is likely",
    "checklist": "Printable Zurich document checklist",
    "articles": "Index of all articles",
    "cantons": "Index of the canton guides",
    "politics": "Politics in your canton: weekly round-ups, votes explained, who's who",
}

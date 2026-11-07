"""Production of one politics page (round-up, vote explainer or who's who): research, the
selection of the week's items, writing, the deterministic checks, the independent neutrality
review (a blocker stops publication), the independent fact review, fixes and translations.

It reuses the article pipeline's production run (app/articles/produce.py) for the cost
tally, the budget guard, the fix loop for format problems and the translations with their
review; the prompts, the payloads and the reviews are politics-specific. The caller has
claimed the page (app/articles/workflow.run_production)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import research
from app.articles.constants import (
    GUIDE_KEYS,
    GUIDE_PAGE_TOPICS,
    KINDS,
    ROUNDUP_ITEMS,
    SEGMENTS,
    VOTE_RESULT_SECTION,
    VOTE_SECTIONS,
    WORDS,
)
from app.articles.produce import (
    ProductionStop,
    Run,
    blocking,
    normalise,
    pending_feedback,
)
from app.articles.validate import validate_article
from app.content import fetch
from app.llm import politics as ai
from app.llm.content import BudgetExceeded, check_budget
from app.models import (
    ART_CHANGES_REQUESTED,
    ART_DRAFTING,
    ART_HELD,
    ART_PUBLISHED,
    ART_READY,
    ART_RESEARCHING,
    ART_REVIEWING,
    Article,
    PoliticsItem,
)
from app.politics import discover
from app.politics.sources import CantonSources, for_canton

log = logging.getLogger(__name__)

NEUTRALITY_FIX_ROUNDS = 1
FACT_FIX_ROUNDS = 2
CANDIDATES_MAX = 30  # item pages fetched for the selection
SELECT_EXCERPT = 1_800
NOMINAL_WORDS = {"roundup": (500, 1100), "vote": (600, 1200), "whoswho": (300, 1000)}
LEVEL_ORDER = {"canton": 0, "city": 1, "federal": 2}


class QuietWeek(ProductionStop):
    """Too few political items this week for a round-up: the week is skipped, not an error."""


def source_record(url: str, title: str, text: str, now: datetime, **extra: Any) -> dict[str, Any]:
    ok = len(text) >= fetch.MIN_TEXT_CHARS
    return {
        "url": url,
        "title": title[:200],
        "fetched_at": now.isoformat(),
        "ok": ok,
        "error": None if ok else "too little readable text",
        "text": text[: research.PAGE_CHARS] if ok else "",
        **extra,
    }


def result_figures(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """The frontmatter's result: yes share, turnout and whether it was accepted."""
    if not result:
        return None
    return {k: result[k] for k in ("yes_percent", "turnout_percent", "accepted")}


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class PoliticsRun(Run):
    """One production run of one politics page."""

    def __init__(self, db: AsyncSession, article: Article, now: datetime):
        super().__init__(db, article, now)
        self.cs: CantonSources | None = for_canton(self.set_canton)
        self.articles: list[dict[str, str]] = []

    @property
    def set_canton(self) -> str:
        return (self.article.plan or {}).get("set_canton") or self.article.canton or "zh"

    @property
    def result(self) -> dict[str, Any] | None:
        return (self.article.plan or {}).get("result") if self.article.kind == "vote" else None

    async def load_context(self) -> None:
        await super().load_context()
        rows = (
            await self.db.execute(
                select(Article.key, Article.plan, Article.english).where(
                    Article.kind.in_(KINDS), Article.status == ART_PUBLISHED
                )
            )
        ).all()
        self.articles = [
            {"key": k, "title": (e or {}).get("title") or (p or {}).get("title", k)}
            for k, p, e in rows
        ]

    async def guard(self) -> None:
        cap = self.settings.politics_cost_cap_chf
        if cap > 0 and self.run_cost >= cap:
            raise ProductionStop(
                f"cost cap reached: this run has cost CHF {self.run_cost:.2f} "
                f"(POLITICS_COST_CAP_CHF {cap:.2f})"
            )
        try:
            await check_budget(self.db)
        except BudgetExceeded as exc:
            raise ProductionStop(f"monthly AI budget reached: {exc}") from exc

    # --- payloads -------------------------------------------------------------------------

    def article_brief(self) -> dict[str, Any]:
        a, plan = self.article, self.article.plan or {}
        low, high = WORDS[a.kind]
        brief: dict[str, Any] = {
            "key": a.key,
            "kind": a.kind,
            "canton": a.canton,
            "canton_name": self.cs.name if self.cs else a.canton,
            "word_range": list(NOMINAL_WORDS[a.kind]),
            "hard_word_limits": [low, high],
            "url_segment": SEGMENTS[a.kind]["en"],
        }
        if a.kind == "roundup":
            brief.update(
                period_start=plan.get("period_start"),
                period_end=plan.get("period_end"),
                items=list(ROUNDUP_ITEMS),
            )
        elif a.kind == "vote":
            brief.update(
                vote_date=plan.get("vote_date"),
                vote_level=plan.get("vote_level"),
                proposal_title_de=plan.get("title_de"),
                sections=list(VOTE_SECTIONS) + ([VOTE_RESULT_SECTION] if self.result else []),
                result=result_figures(self.result),
            )
        elif a.kind == "whoswho":
            brief.update(
                roster=plan.get("roster") or {},
                kantonsrat_seats=plan.get("seats") or {},
                seats_counted=sum((plan.get("seats") or {}).values()),
                seats_note=(
                    "Counted from the Kantonsrat's member list, one seat per member listed. If the "
                    "total is below the number of seats the pages state, say that the list "
                    "shows that many members (a seat may be vacant); do not adjust the numbers."
                ),
            )
        return brief

    def link_targets(self) -> dict[str, Any]:
        return {
            "guide_pages": {
                k: GUIDE_PAGE_TOPICS.get(k, k) for k in GUIDE_KEYS if k in GUIDE_PAGE_TOPICS
            },
            "articles": self.articles[:30],
        }

    def sources(self) -> list[dict[str, str]]:
        plan = self.article.plan or {}
        focus = " ".join(
            str(x) for x in (plan.get("title_de"), plan.get("title"), plan.get("vote_date")) if x
        )
        return research.excerpts(self.article.sources_read, focus)

    def problems(self, content: dict[str, Any]) -> list[str]:
        return validate_article(
            content,
            kind=self.article.kind,
            lang="en",
            plan_keys=self.plan_keys,
            read_urls=research.read_urls(self.article.sources_read),
            has_result=bool(self.result),
        )

    # --- calls ------------------------------------------------------------------------------

    async def write(self) -> dict[str, Any]:
        s = self.settings
        payload = {
            "today": self.today(),
            "page": self.article_brief(),
            "owner_feedback": [f["text"] for f in pending_feedback(self.article)],
            "links": self.link_targets(),
            "sources": self.sources(),
        }
        data = await self.ask(
            ai.PURPOSE_WRITE,
            ai.PROMPT_WRITE[self.article.kind],
            s.politics_write_model,
            payload,
            ai.PAGE_SCHEMA,
            s.articles_effort,
        )
        return normalise(data)

    async def fix(
        self,
        content: dict[str, Any],
        *,
        findings: list[dict[str, Any]],
        owner_feedback: list[str] | None = None,
        kind: str,
    ) -> tuple[dict[str, Any], list[str]]:
        s = self.settings
        payload = {
            "today": self.today(),
            "reason": kind,
            "owner_feedback": owner_feedback or [],
            "findings": findings,
            "page": self.article_brief(),
            "links": self.link_targets(),
            "current_version": content,
            "sources": self.sources(),
        }
        data = await self.ask(
            ai.PURPOSE_FIX,
            ai.PROMPT_FIX,
            s.politics_write_model,
            payload,
            ai.PAGE_FIX_SCHEMA,
            s.articles_effort,
        )
        return normalise(data), [str(c) for c in data.get("changes") or []]

    async def _review(self, kind: str, content: dict[str, Any]) -> list[dict[str, Any]]:
        s = self.settings
        purpose, prompt = (
            (ai.PURPOSE_NEUTRALITY, ai.PROMPT_NEUTRALITY)
            if kind == "neutrality"
            else (ai.PURPOSE_REVIEW, ai.PROMPT_REVIEW)
        )
        payload = {
            "today": self.today(),
            "page": self.article_brief(),
            "version": content,
            "sources": self.sources(),
        }
        schema = ai.NEUTRALITY_SCHEMA if kind == "neutrality" else ai.FACT_REVIEW_SCHEMA
        data = await self.ask(
            purpose, prompt, s.politics_review_model, payload, schema, s.articles_effort,
            max_tokens=12_000,
        )  # fmt: skip
        findings = [f for f in data.get("findings") or [] if isinstance(f, dict)]
        self.note(
            {
                "kind": f"{kind}_review",
                "verdict": data.get("verdict"),
                "findings": findings,
                "model": s.politics_review_model,
            }
        )
        return findings

    async def reviewed(self, kind: str, content: dict[str, Any], rounds: int) -> dict[str, Any]:
        """Review, fix and review again, at most `rounds` fixes; a blocker or major finding
        left after them stops the run."""
        for rnd in range(rounds + 1):
            findings = await self._review(kind, content)
            if not blocking(findings):
                return content
            if rnd == rounds:
                raise ProductionStop(
                    f"the {kind} review still finds problems after {rounds} fix round(s)",
                    blocking(findings),
                )
            content, changes = await self.fix(content, findings=findings, kind=f"{kind}_review")
            self.note({"kind": "fix", "reason": f"{kind}_review", "round": rnd + 1,
                       "changes": changes})  # fmt: skip
            content = await self.ensure_valid(content)
        raise AssertionError("unreachable")

    async def english(self, feedback: list[dict[str, Any]]) -> dict[str, Any]:
        await self.set_status(ART_DRAFTING)
        content = await self.ensure_valid(await self.write())
        await self.set_status(ART_REVIEWING)
        content = await self.reviewed("neutrality", content, NEUTRALITY_FIX_ROUNDS)
        before = content
        content = await self.reviewed("fact", content, FACT_FIX_ROUNDS)
        if content is not before:  # the fact fixes changed the text: neutral still?
            content = await self.reviewed("neutrality", content, 0)
        out = {**content, "checked": self.today()}
        if self.result:  # the frontmatter's result: the three figures only
            out["result"] = result_figures(self.result)
        return out

    # --- research ---------------------------------------------------------------------------

    async def research(self) -> list[dict[str, Any]]:
        kind = self.article.kind
        if kind == "roundup":
            return await self.research_roundup()
        if kind == "vote":
            return await self.research_vote()
        return await self.research_whoswho()

    async def fetch_pages(self, urls: list[tuple[str, str]]) -> list[dict[str, Any]]:
        allowed = [(u, t) for u, t in urls if self.cs is None or self.cs.host_allowed(u)]
        async with fetch.new_client() as client:
            pages = await fetch.gather_limited([fetch.fetch_page(client, u) for u, _ in allowed], 4)
        return [
            source_record(u, t, p.text if p.readable else "", self.now)
            for (u, t), p in zip(allowed, pages, strict=True)
        ]

    async def research_roundup(self) -> list[dict[str, Any]]:
        plan = self.article.plan
        start, end = _date(plan["period_start"]), _date(plan["period_end"])
        items = (
            (
                await self.db.execute(
                    select(PoliticsItem).where(
                        PoliticsItem.canton == self.set_canton,
                        PoliticsItem.item_date >= start,
                        PoliticsItem.item_date <= end,
                        PoliticsItem.source_type.in_(("listing", "rss", "vote_list")),
                        PoliticsItem.level.in_(("canton", "city")),
                    )
                )
            )
            .scalars()
            .all()
        )
        items = sorted(items, key=lambda i: (LEVEL_ORDER.get(i.level, 3), i.item_date, i.title))
        seen: set[str] = set()
        picked = []
        for i in items:
            if i.url not in seen:
                seen.add(i.url)
                picked.append(i)
        picked = picked[:CANDIDATES_MAX]
        pages = await self.fetch_pages([(i.url, i.title) for i in picked])
        by_url = {p["url"]: p for p in pages}
        candidates = [
            {
                "url": i.url,
                "title_de": i.title,
                "date": i.item_date.isoformat() if i.item_date else None,
                "level": i.level,
                "source": i.source_id,
                "excerpt": by_url[i.url]["text"][:SELECT_EXCERPT],
            }
            for i in picked
            if by_url.get(i.url, {}).get("ok")
        ]
        low, high = ROUNDUP_ITEMS
        if len(candidates) < low:
            raise QuietWeek(
                f"quiet week: only {len(candidates)} readable item(s) between {start} and {end}"
            )
        s = self.settings
        data = await self.ask(
            ai.PURPOSE_SELECT,
            ai.PROMPT_SELECT,
            s.politics_select_model,
            {
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "canton": self.cs.name if self.cs else self.set_canton,
                "items_wanted": [low, high],
                "candidates": candidates,
            },
            ai.SELECT_SCHEMA,
            "medium",
            max_tokens=4000,
        )
        chosen = []
        for c in data.get("items") or []:
            url = str(c.get("url", ""))
            if url in by_url and by_url[url]["ok"] and url not in chosen:
                chosen.append(url)
        chosen = chosen[:high]
        self.note({"kind": "selection", "chosen": chosen, "quiet_week": data.get("quiet_week")})
        if data.get("quiet_week") or len(chosen) < low:
            raise QuietWeek(f"quiet week: the selection found {len(chosen)} political item(s)")
        return [by_url[u] for u in chosen]

    async def research_vote(self) -> list[dict[str, Any]]:
        plan = self.article.plan
        out: list[dict[str, Any]] = []
        title = plan.get("title_de") or plan.get("title") or ""
        if plan.get("vote_level") == "federal":
            affairs = (
                (
                    await self.db.execute(
                        select(PoliticsItem).where(
                            PoliticsItem.canton == self.set_canton,
                            PoliticsItem.source_id == "ch-parlament-votes",
                        )
                    )
                )
                .scalars()
                .all()
            )
            same_day = [a for a in affairs if (a.data or {}).get("vote_date") == plan["vote_date"]]
            best = sorted(same_day, key=lambda a: -discover.title_overlap(a.title, title))
            async with fetch.new_client() as client:
                if best and discover.title_overlap(best[0].title, title) >= 1:
                    aff = await discover.fetch_affair(client, best[0].data["affair"]["affair_id"])
                    out.append(source_record(aff["url"], aff["title"], aff["text"], self.now,
                                             read_url=aff["read_url"]))  # fmt: skip
            if same_day:
                out += await self.fetch_pages(
                    [
                        (
                            "https://www.parlament.ch/de/services/volksabstimmungen",
                            "Federal Assembly: federal votes",
                        )
                    ]  # fmt: skip
                )
        else:
            urls = [(u, title) for u in plan.get("announcements") or []]
            related = (
                (
                    await self.db.execute(
                        select(PoliticsItem).where(
                            PoliticsItem.canton == self.set_canton,
                            PoliticsItem.level == "canton",
                        )
                    )
                )
                .scalars()
                .all()
            )
            scored = sorted(related, key=lambda i: -discover.title_overlap(i.title, title))
            urls += [
                (i.url, i.title) for i in scored[:5] if discover.title_overlap(i.title, title) >= 2
            ]
            out += await self.fetch_pages(list(dict.fromkeys(urls)))
        result = self.result
        if result and result.get("source_url"):
            if result.get("source_text"):
                out.append(source_record(result["source_url"], result.get("source_title", ""),
                                         result["source_text"], self.now))  # fmt: skip
            else:
                out += await self.fetch_pages([(result["source_url"], "Vote result")])
        dedup: dict[str, dict[str, Any]] = {}
        for s in out:
            dedup.setdefault(s["url"], s)
        return list(dedup.values())

    async def research_whoswho(self) -> list[dict[str, Any]]:
        # The monthly check (app/politics/schedule.py) has just read the people pages.
        return list(self.article.sources_read or [])


async def produce(db: AsyncSession, article: Article, now: datetime) -> str:
    """Run production for a claimed politics page. Returns the new status: ready (the tick
    then publishes it), changes_requested, held (a quiet week) or needs_attention."""
    from app.articles import workflow

    run = PoliticsRun(db, article, now)
    feedback = pending_feedback(article)
    try:
        await run.load_context()
        await run.set_status(ART_RESEARCHING)
        if article.kind != "whoswho" or not article.sources_read:
            article.sources_read = await run.research()
            await db.commit()
        n = len(research.readable(article.sources_read))
        need = {"roundup": ROUNDUP_ITEMS[0], "vote": 1, "whoswho": 3}[article.kind]
        if n < need:
            raise ProductionStop(f"only {n} source page(s) could be read; at least {need} needed")
        english = await run.english(feedback)
        translations = await run.translations(english)
    except QuietWeek as quiet:
        article.status = ART_HELD
        article.last_error = quiet.reason
        article.production_started_at = None
        article.reviews = [*(article.reviews or []), {"at": now.isoformat(), "kind": "skipped",
                                                       "reason": quiet.reason}]  # fmt: skip
        await db.commit()
        log.info("Politics %s: %s", article.key, quiet.reason)
        return article.status
    except ProductionStop as stop:
        if run.draft is not None:
            article.english = run.draft
            article.translations = {}
            article.revision += 1
        await workflow.mark_needs_attention(db, article, stop.reason, stop.findings, now)
        return article.status
    except Exception as exc:  # noqa: BLE001  any other failure stops the run the same way
        log.exception("Politics %s: production failed", article.key)
        await db.rollback()
        article = await db.get(Article, article.id)
        await workflow.mark_needs_attention(
            db, article, f"unexpected error: {exc.__class__.__name__}", [], now
        )
        return article.status

    await db.refresh(article, ["feedback"])
    used = {f["id"] for f in feedback}
    article.feedback = [
        {**f, "applied_revision": article.revision + 1} if f.get("id") in used else f
        for f in article.feedback or []
    ]
    article.english = english
    article.translations = translations
    article.revision += 1
    article.production_started_at = None
    article.last_error = None
    article.attempts = 0
    article.status = ART_CHANGES_REQUESTED if pending_feedback(article) else ART_READY
    await db.commit()
    log.info(
        "Politics %s: revision %d %s (CHF %.2f this run)",
        article.key,
        article.revision,
        article.status,
        run.run_cost,
    )
    return article.status

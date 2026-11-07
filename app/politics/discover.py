"""Discovery: read the listings, feeds and vote lists of content/politics/sources.yaml, keep
what they list in `politics_items`, and turn announced votes into vote pages to write.

The parsers are deterministic and work on the text the sources return (tests run them on
saved copies in tests/fixtures/politics/). Only when an HTML listing yields no dated link at
all is a cheap model call asked to pick the item links (prompt politics/links), and a vote
announcement's proposals are listed by one (politics/proposals), since the government names
them in running text.

Only public pages of the authorities are read; nothing about learners is ever sent."""

from __future__ import annotations

import html as htmllib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.plan import new_nonce
from app.config import get_settings
from app.content import fetch
from app.llm import articles as llm
from app.llm import politics as ai
from app.models import ART_PLANNED, Article, PoliticsItem
from app.politics.sources import CantonSources, Source
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

MAX_LISTING_BYTES = 3 * 1024 * 1024
FEDERAL_LOOKBACK = timedelta(days=75)  # results arrive some weeks after the vote
PUBLISH_HOUR = 7  # politics pages go out at 07:00 Zurich time

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}  # fmt: skip
DATE_DOTTED = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
DATE_LONG = re.compile(r"\b(\d{1,2})\.\s*(" + "|".join(MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE)
RESULT_TITLE = re.compile(r"(?i)\b(ausgang|resultat|ergebnis)")
NO_VOTE_TITLE = re.compile(r"(?i)\bkeine\b.*\babstimmungsvorlage")


@dataclass
class Entry:
    url: str
    title: str
    item_date: date | None
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)


# --- dates -----------------------------------------------------------------------------------


def find_date(text: str) -> date | None:
    """The first date in a German text: 05.11.2026 or 6. November 2026."""
    candidates: list[tuple[int, date]] = []
    for m in DATE_DOTTED.finditer(text):
        try:
            candidates.append((m.start(), date(int(m[3]), int(m[2]), int(m[1]))))
        except ValueError:
            continue
    for m in DATE_LONG.finditer(text):
        try:
            candidates.append((m.start(), date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))))
        except ValueError:
            continue
    return min(candidates)[1] if candidates else None


def zurich_date(moment: datetime) -> date:
    return moment.astimezone(ZURICH).date()


def zurich_at(day: date, hour: int = PUBLISH_HOUR) -> datetime:
    return datetime.combine(day, time(hour, 0), tzinfo=ZURICH).astimezone(UTC)


def _clean(text: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", text or "")).split())


def slugify(text: str, max_words: int = 6, max_len: int = 48) -> str:
    """An ASCII slug from a German title: umlauts as ae/oe/ue, no stop-word padding."""
    t = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    # A federal proposal's title starts with its legal form and date; the name follows.
    t = re.sub(r"^.*?\bvom\s+\d{1,2}\.\d{1,2}\.\d{4}\s*", "", t) or t
    stop = {"der", "die", "das", "des", "dem", "den", "ein", "eine", "und", "fuer", "zur", "zum",
            "von", "vom", "im", "in", "am", "an", "auf", "mit", "ueber", "zu", "bei"}  # fmt: skip
    words = [w for w in re.findall(r"[a-z0-9]+", t) if w not in stop]
    slug = "-".join(words[:max_words])[:max_len].strip("-")
    return slug or "vorlage"


# --- parsers (pure) ----------------------------------------------------------------------------


def parse_zhweb_news(text: str, base: str = "https://www.zh.ch") -> list[Entry]:
    """The JSON behind zh.ch's news overview: {"news": [{title, date, type, link, ...}]}."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for n in data.get("news") or []:
        if not isinstance(n, dict) or not n.get("link") or not n.get("title"):
            continue
        out.append(
            Entry(
                url=urljoin(base, str(n["link"])),
                title=_clean(str(n["title"])),
                item_date=find_date(str(n.get("date", ""))),
                summary=_clean(str(n.get("teaserText", "")))[:600],
                data={"type": str(n.get("type", ""))},
            )
        )
    return out


_ITEM_RE = re.compile(r"<item\b[^>]*>(.*?)</item>", re.S | re.I)


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", block, re.S | re.I)
    if not m:
        return ""
    value = m.group(1).strip()
    cdata = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", value, re.S)
    return cdata.group(1) if cdata else htmllib.unescape(value)


def parse_rss(text: str) -> list[Entry]:
    """RSS 2.0 items (title, link, pubDate, description). A plain parser on purpose: no XML
    entity expansion from a remote document."""
    out = []
    for block in _ITEM_RE.findall(text):
        url = _clean(_tag(block, "link"))
        title = _clean(_tag(block, "title"))
        if not url.startswith("https://") or not title:
            continue
        day = None
        raw_date = _clean(_tag(block, "pubDate"))
        if raw_date:
            try:
                day = zurich_date(parsedate_to_datetime(raw_date))
            except (TypeError, ValueError):
                day = find_date(raw_date)
        out.append(Entry(url, title, day, _clean(_tag(block, "description"))[:600]))
    return out


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ("a", "link", "base") and "-" in tag:
            # A web component that links (the city of Zurich: <stzh-card-superteaser
            # heading="..." href="...">): its label is an attribute.
            a = dict(attrs)
            if a.get("href"):
                self.links.append((a["href"], a.get("heading") or a.get("text") or ""))
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href and self._href is None:
                self._href, self._text, self._depth = href, [], 1
            elif self._href is not None:
                self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self._depth -= 1
            if self._depth <= 0:
                self.links.append((self._href, " ".join(" ".join(self._text).split())))
                self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


def anchors(page: str) -> list[tuple[str, str]]:
    parser = _Anchors()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001, S110  a broken page still gives what was parsed
        pass
    return parser.links


def parse_html_dated(page: str, base: str, include: str | None = None) -> list[Entry]:
    """Links whose text carries a date ("05.11.2026 Bulletin Beschlüsse des Kantonsrates");
    the title is the text without the date. `include` filters on the text."""
    out: list[Entry] = []
    seen: set[str] = set()
    pattern = re.compile(include) if include else None
    for href, text in anchors(page):
        day = find_date(text)
        if day is None or (pattern and not pattern.search(text)):
            continue
        url = urljoin(base, href)
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        title = DATE_LONG.sub("", DATE_DOTTED.sub("", text)).strip(" -–|·")
        out.append(Entry(url, " ".join(title.split())[:300], day))
    return out


def parse_lindas(text: str) -> list[dict[str, Any]]:
    """Federal proposals from the Federal Chancellery's open vote data (SPARQL JSON)."""
    try:
        rows = json.loads(text)["results"]["bindings"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for row in rows:
        v = {k: (row.get(k) or {}).get("value", "") for k in row}
        try:
            day = date.fromisoformat(v.get("date", "")[:10])
        except ValueError:
            continue
        result = None
        if v.get("yesPercentage") and v.get("voterTurnout"):
            text_result = v.get("voteResult", "").lower()
            if "angenommen" in text_result or "abgelehnt" in text_result:
                result = {
                    "yes_percent": round(float(v["yesPercentage"]), 2),
                    "turnout_percent": round(float(v["voterTurnout"]), 2),
                    "accepted": "angenommen" in text_result,
                }
        out.append(
            {
                "id": v.get("id", ""),
                "date": day.isoformat(),
                "title": " ".join(v.get("title", "").split()),
                "status": v.get("voteResult", ""),
                "result": result,
            }
        )
    return out


AFFAIR_RE = re.compile(r"AffairId(?:=|%3D)(\d{8})")


def parse_parlament_votes(page: str) -> dict[str, Any]:
    """parlament.ch's next federal vote: its date and each proposal's business id."""
    text = fetch.html_to_text(page)
    vote_date = None
    m = re.search(r"Volksabstimmung vom\s+(.{5,40}?\d{4})", text, re.I)
    if m:
        vote_date = find_date(m.group(1).replace("\xa0", " "))
    affairs: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, _ in anchors(page):
        found = AFFAIR_RE.search(href)
        if found and found.group(1) not in seen:
            seen.add(found.group(1))
            affairs.append({"affair_id": found.group(1)})
    # Titles: the line after each business number (24.080) in the page text.
    lines = [line.strip().replace("​", "") for line in text.splitlines()]
    titles = []
    for i, line in enumerate(lines):
        if re.fullmatch(r"\d{2}\.\d{3}", line) and i + 1 < len(lines):
            titles.append((line, lines[i + 1]))
    for affair, (number, title) in zip(affairs, titles, strict=False):
        affair["number"] = number
        affair["title"] = title
    return {"vote_date": vote_date.isoformat() if vote_date else None, "affairs": affairs}


PARTIES = ("SVP", "SP", "FDP", "GLP", "Grüne", "Die Mitte", "EVP", "AL", "EDU", "parteilos")


def party_seats(text: str) -> dict[str, int]:
    """Seats per party, counted from a member list with one party label per line (the
    Kantonsrat's member page). A trailing dash marks a role and is ignored."""
    counts: dict[str, int] = {}
    for line in text.splitlines():
        label = line.strip().rstrip("–-* ").strip()
        if label in PARTIES:
            counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def linked_pages(page: str, base: str, pattern: str) -> list[str]:
    rx = re.compile(pattern)
    out: list[str] = []
    for href, _ in anchors(page):
        url = urljoin(base, href)
        if rx.search(urlsplit(url).path) and url not in out:
            out.append(url)
    return out


# --- fetching -----------------------------------------------------------------------------------


async def fetch_raw(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    content: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """(text, None) or (None, error). At most MAX_LISTING_BYTES."""
    try:
        async with client.stream(method, url, content=content, headers=headers) as r:
            if r.status_code >= 400:
                return None, f"HTTP {r.status_code}"
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_LISTING_BYTES:
                    break
            return b"".join(chunks).decode(r.encoding or "utf-8", errors="replace"), None
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.HTTPError as exc:
        return None, exc.__class__.__name__


LINDAS_QUERY = """PREFIX cube: <https://cube.link/>
PREFIX schema: <http://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX vote: <https://politics.ld.admin.ch/political-rights/popular-vote/>
SELECT DISTINCT ?date ?id ?title ?yesPercentage ?voterTurnout ?voteResult WHERE {
  ?obs a cube:Observation ; vote:date ?date ; vote:id ?id ;
       vote:abstimmungstitel ?titleUri ; vote:ergebnis ?resultUri .
  OPTIONAL { ?obs vote:region ?region . }
  FILTER(!BOUND(?region) || ?region = <https://ld.admin.ch/country/CHE>)
  FILTER(?date >= "%(since)s"^^xsd:date)
  ?titleUri schema:name ?title . FILTER(LANGMATCHES(LANG(?title), "de"))
  OPTIONAL { ?obs vote:jaAnteil ?yesPercentage ; vote:stimmbeteiligung ?voterTurnout . }
  OPTIONAL { ?resultUri schema:name ?voteResult . FILTER(LANGMATCHES(LANG(?voteResult), "de")) }
} ORDER BY ?date ?id"""


async def read_source(
    client: httpx.AsyncClient, source: Source, today: date
) -> tuple[list[Entry], list[str]]:
    """The entries of one listing, feed or vote list, and any errors."""
    errors: list[str] = []
    entries: list[Entry] = []
    if source.format == "lindas_votes":
        query = LINDAS_QUERY % {"since": (today - FEDERAL_LOOKBACK).isoformat()}
        text, err = await fetch_raw(
            client,
            source.url,
            method="POST",
            content=query,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        if err:
            return [], [f"{source.id}: {err}"]
        for p in parse_lindas(text or ""):
            cite = (source.cite or source.url).replace("{date}", p["date"])
            entries.append(
                Entry(
                    f"{cite}#vorlage-{p['id']}",
                    p["title"],
                    date.fromisoformat(p["date"]),
                    data={"federal": p, "cite": cite},
                )  # fmt: skip
            )
        return entries, errors
    pages = [source.url]
    if source.format == "zhweb_news":
        sep = "&" if "?" in source.url else "?"
        pages += [f"{source.url}{sep}page={n}" for n in range(2, source.pages + 1)]
    for url in pages:
        text, err = await fetch_raw(client, url)
        if err:
            errors.append(f"{source.id}: {err}")
            continue
        text = text or ""
        if source.format == "zhweb_news":
            entries += parse_zhweb_news(text)
        elif source.format == "rss":
            entries += parse_rss(text)
        elif source.format == "html_dated":
            entries += parse_html_dated(text, source.url, source.include)
        elif source.format == "parlament_votes":
            parsed = parse_parlament_votes(text)
            for a in parsed["affairs"]:
                entries.append(
                    Entry(
                        affair_url(a["affair_id"]),
                        a.get("title") or a.get("number") or a["affair_id"],
                        date.fromisoformat(parsed["vote_date"]) if parsed["vote_date"] else None,
                        data={"affair": a, "vote_date": parsed["vote_date"]},
                    )
                )
    if source.title_match:
        rx = re.compile(source.title_match)
        entries = [e for e in entries if rx.search(e.title)]
    return entries, errors


def affair_url(affair_id: str) -> str:
    return (
        f"https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={affair_id}"
    )


def affair_data_url(affair_id: str) -> str:
    return (
        "https://ws.parlament.ch/odata.svc/Business?$filter=ID%20eq%20"
        f"{affair_id}%20and%20Language%20eq%20%27DE%27&$format=json"
    )


async def fetch_affair(client: httpx.AsyncClient, affair_id: str) -> dict[str, Any]:
    """A federal business from parlament.ch's data service, as a source: the Federal
    Council's message and the debates (their text), cited as its Curia Vista page."""
    text, err = await fetch_raw(client, affair_data_url(affair_id))
    out: dict[str, Any] = {"url": affair_url(affair_id), "read_url": affair_data_url(affair_id)}
    if err or not text:
        return {**out, "ok": False, "error": err or "empty", "text": "", "title": affair_id}
    try:
        data = json.loads(text)["d"]
        row = (data if isinstance(data, list) else data.get("results", []))[0]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return {**out, "ok": False, "error": "no data", "text": "", "title": affair_id}
    parts = [
        row.get("Title") or "",
        row.get("Description") or "",
        fetch.html_to_text(row.get("InitialSituation") or ""),
        fetch.html_to_text(row.get("Proceedings") or ""),
    ]
    body = "\n".join(p for p in parts if p)
    title = f"Federal Assembly: {row.get('BusinessShortNumber', '')} {row.get('Title', '')}"
    return {
        **out,
        "ok": len(body) >= fetch.MIN_TEXT_CHARS,
        "error": None,
        "text": body,
        "title": " ".join(title.split())[:200],
    }


# --- the item store -----------------------------------------------------------------------------


async def store(
    db: AsyncSession, canton: str, source: Source, entries: list[Entry], now: datetime
) -> list[PoliticsItem]:
    """Insert new items, refresh the data of known ones. Returns the new items."""
    if not entries:
        return []
    urls = [e.url[:600] for e in entries]
    known = {
        i.url: i
        for i in (
            await db.execute(
                select(PoliticsItem).where(
                    PoliticsItem.canton == canton, PoliticsItem.url.in_(urls)
                )
            )
        ).scalars()
    }
    new: list[PoliticsItem] = []
    for e in entries:
        url = e.url[:600]
        row = known.get(url)
        data = {**e.data, "summary": e.summary} if e.summary else dict(e.data)
        if row is None:
            row = PoliticsItem(
                canton=canton,
                source_id=source.id,
                source_type=source.type,
                level=source.level,
                url=url,
                title=e.title[:400],
                item_date=e.item_date,
                data=data,
                discovered_at=now,
            )
            db.add(row)
            known[url] = row
            new.append(row)
        else:
            if source.type == "vote_list" and row.source_type != "vote_list":
                # The same news item is also a vote announcement: that role wins.
                row.source_type, row.source_id = source.type, source.id
            if row.data != data:
                row.data = {**(row.data or {}), **data}
    await db.commit()
    return new


@dataclass
class DiscoveryReport:
    canton: str
    found: dict[str, int] = field(default_factory=dict)
    new: int = 0
    votes_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cost_chf: float = 0.0

    def summary(self) -> str:
        found = ", ".join(f"{k} {v}" for k, v in self.found.items())
        return (
            f"Discovery {self.canton}: {self.new} new item(s) ({found}); "
            f"{len(self.votes_created)} vote page(s) created; {len(self.errors)} error(s)"
        )


async def ai_links(
    page_text: str, links: list[tuple[str, str]], source: Source
) -> tuple[list[Entry], llm.CallResult]:
    """Fallback for a listing that yields no dated link: a cheap model picks the items."""
    s = get_settings()
    result = await llm.call(
        purpose=ai.PURPOSE_LINKS,
        prompt_name=ai.PROMPT_LINKS,
        model=s.politics_extract_model,
        payload={
            "source": source.purpose,
            "page_text": page_text[:12_000],
            "links": [{"url": u, "text": t[:200]} for u, t in links[:300]],
        },
        schema=ai.LINKS_SCHEMA,
        effort="low",
        max_tokens=4000,
    )
    out = []
    allowed = {u for u, _ in links}
    for item in (result.data or {}).get("items") or []:
        url = str(item.get("url", ""))
        if url in allowed:
            out.append(
                Entry(url, str(item.get("title", ""))[:300], find_date(item.get("date", "")))
            )
    return out, result


async def discover(
    db: AsyncSession, cs: CantonSources, now: datetime, *, use_ai: bool = True
) -> DiscoveryReport:
    """Read every listing, feed and vote list of the canton, store the items, and create
    the vote pages of newly announced votes. Never raises for a source that fails."""
    report = DiscoveryReport(cs.canton)
    today = zurich_date(now)
    async with fetch.new_client() as client:
        for source in cs.of_type("listing", "rss", "vote_list"):
            entries, errors = await read_source(client, source, today)
            report.errors += errors
            if not entries and not errors and source.format == "html_dated" and use_ai:
                text, err = await fetch_raw(client, source.url)
                if text:
                    entries, call = await ai_links(
                        fetch.html_to_text(text),
                        [(urljoin(source.url, h), t) for h, t in anchors(text)],
                        source,
                    )
                    report.cost_chf += await llm.record(db, call)
            entries = [
                e for e in entries if source.format == "lindas_votes" or cs.host_allowed(e.url)
            ]
            report.found[source.id] = len(entries)
            report.new += len(await store(db, cs.canton, source, entries, now))
        report.votes_created += await federal_votes(db, cs, now)
        created, cost = await cantonal_votes(db, cs, client, now, use_ai=use_ai)
        report.votes_created += created
        report.cost_chf += cost
    log.info(report.summary())
    return report


# --- votes --------------------------------------------------------------------------------------


def vote_key(canton: str, vote_date: str, name: str) -> str:
    return f"vote-{canton}-{vote_date}-{slugify(name)}"[:80].rstrip("-")


def vote_publish_at(vote_date: date, now: datetime) -> datetime:
    lead = timedelta(days=get_settings().politics_vote_lead_days)
    return max(zurich_at(vote_date - lead), now)


async def ensure_vote(
    db: AsyncSession,
    *,
    set_canton: str,
    canton: str,
    level: str,
    vote_date: date,
    title_de: str,
    name: str,
    data: dict[str, Any],
    now: datetime,
) -> str | None:
    """Create the vote page's row if it does not exist. Returns its key when created."""
    key = vote_key(canton, vote_date.isoformat(), name)
    exists = await db.scalar(select(Article.id).where(Article.key == key))
    if exists is not None:
        return None
    db.add(
        Article(
            key=key,
            kind="vote",
            category="politics",
            canton=canton,
            publish_at=vote_publish_at(vote_date, now),
            status=ART_PLANNED,
            plan={
                "key": key,
                "kind": "vote",
                "title": title_de[:200],
                "title_de": title_de,
                "vote_date": vote_date.isoformat(),
                "vote_level": level,
                "set_canton": set_canton,
                "result": None,
                **data,
            },
            translations={},
            reviews=[],
            feedback=[],
            sources_read=[],
            live_urls={},
            live_files={},
            review_nonce=new_nonce(),
        )
    )
    await db.commit()
    log.info("Politics: vote page %s created (vote on %s)", key, vote_date)
    return key


async def federal_votes(db: AsyncSession, cs: CantonSources, now: datetime) -> list[str]:
    """Every federal proposal still ahead gets a page (canton ch); results are copied onto
    pages already published (app/politics/schedule.py re-publishes them)."""
    today = zurich_date(now)
    rows = (
        await db.execute(
            select(PoliticsItem).where(
                PoliticsItem.canton == cs.canton, PoliticsItem.source_id == "ch-federal-votes"
            )
        )
    ).scalars()
    created = []
    for item in rows:
        p = (item.data or {}).get("federal") or {}
        if not p.get("date"):
            continue
        day = date.fromisoformat(p["date"])
        if day > today:
            key = await ensure_vote(
                db,
                set_canton=cs.canton,
                canton="ch",
                level="federal",
                vote_date=day,
                title_de=p["title"],
                name=p["title"],
                data={"federal_id": p.get("id"), "cite": item.data.get("cite")},
                now=now,
            )
            if key:
                created.append(key)
    return created


async def cantonal_votes(
    db: AsyncSession, cs: CantonSources, client: httpx.AsyncClient, now: datetime, *, use_ai: bool
) -> tuple[list[str], float]:
    """Vote announcements of the canton's government not yet read: the page is fetched and a
    cheap model lists the proposals and the date. Result notices are kept for later."""
    rows = (
        (
            await db.execute(
                select(PoliticsItem).where(
                    PoliticsItem.canton == cs.canton,
                    PoliticsItem.source_type == "vote_list",
                    PoliticsItem.level == "canton",
                    PoliticsItem.processed_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    created: list[str] = []
    cost = 0.0
    today = zurich_date(now)
    for item in rows:
        if RESULT_TITLE.search(item.title) or NO_VOTE_TITLE.search(item.title):
            item.processed_at = now  # results are read by the result check; "no vote" is news
            continue
        if not use_ai:
            continue
        page = await fetch.fetch_page(client, item.url)
        if not page.readable:
            continue
        s = get_settings()
        result = await llm.call(
            purpose=ai.PURPOSE_PROPOSALS,
            prompt_name=ai.PROMPT_PROPOSALS,
            model=s.politics_extract_model,
            payload={"title": item.title, "date": str(item.item_date), "text": page.text[:12_000]},
            schema=ai.PROPOSALS_SCHEMA,
            effort="low",
            max_tokens=2000,
        )
        cost += await llm.record(db, result)
        if not result.ok:
            continue
        item.processed_at = now
        data = result.data or {}
        try:
            vote_date = date.fromisoformat(str(data.get("vote_date", ""))[:10])
        except ValueError:
            vote_date = find_date(item.title)
        if vote_date is None or vote_date <= today:
            continue
        for prop in data.get("proposals") or []:
            title = " ".join(str(prop.get("title_de", "")).split())
            if not title:
                continue
            key = await ensure_vote(
                db,
                set_canton=cs.canton,
                canton=cs.canton,
                level="cantonal",
                vote_date=vote_date,
                title_de=title,
                name=str(prop.get("short_name") or title),
                data={"announcements": [item.url]},
                now=now,
            )
            if key:
                created.append(key)
    await db.commit()
    return created, cost


def title_overlap(a: str, b: str) -> int:
    words = lambda s: set(re.findall(r"[a-zäöü]{5,}", s.lower()))  # noqa: E731
    return len(words(a) & words(b))

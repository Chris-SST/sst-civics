"""Fetching the official pages a question cites (source check, link check; task 1.5).

httpx only, with a timeout, a descriptive user agent and a 2 MB cap per page. HTML is
reduced to plain text with the standard library's parser. Nothing about learners is ever
sent: the only request data is the public URL."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import httpx

USER_AGENT = "civics-trainer-source-check/1.0 (checks cited public pages; contact via website)"
TIMEOUT_SECONDS = 20.0
MAX_BYTES = 2 * 1024 * 1024
MIN_TEXT_CHARS = 200  # less than this is not a readable page (often a JavaScript shell)

# Hosts a draft question may cite (PLAN.md: admin.ch, ch.ch, the canton or the commune).
OFFICIAL_HOSTS = ("admin.ch", "ch.ch", "parlament.ch", "zh.ch", "ag.ch", "stadt-zuerich.ch")


def is_official_url(url: str, *, commune: bool = False) -> bool:
    """https and a federal, cantonal or (for commune questions) any .ch host."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    if any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
        return True
    return commune and host.endswith(".ch")


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "de-CH,de;q=0.9"},
    )


# --- HTML to text --------------------------------------------------------------------------

_SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
_BLOCK = {
    "p",
    "div",
    "section",
    "article",
    "li",
    "ul",
    "ol",
    "tr",
    "table",
    "br",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "dt",
    "dd",
    "blockquote",
    "header",
    "footer",
    "main",
    "nav",
}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.title: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001, S110  a broken page still gives what was parsed
        pass
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", line).strip() for line in text.split("\n")]
    body = "\n".join(line for line in lines if line)
    title = " ".join("".join(parser.title).split())
    return f"{title}\n{body}" if title and not body.startswith(title) else body


# --- Fetching -------------------------------------------------------------------------------


@dataclass
class Page:
    url: str
    ok: bool  # the server answered with a page (status below 400)
    status: int | None = None
    text: str = ""
    error: str | None = None  # why the page could not be read: "HTTP 404", "timeout", ...
    truncated: bool = False

    @property
    def readable(self) -> bool:
        return self.ok and len(self.text) >= MIN_TEXT_CHARS


async def fetch_page(client: httpx.AsyncClient, url: str, max_bytes: int = MAX_BYTES) -> Page:
    """GET a page and return its text, reading at most `max_bytes`."""
    try:
        async with client.stream("GET", url) as response:
            if response.status_code >= 400:
                return Page(url, False, response.status_code, error=f"HTTP {response.status_code}")
            chunks: list[bytes] = []
            size = 0
            truncated = False
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= max_bytes:
                    truncated = True
                    break
            raw = b"".join(chunks)[:max_bytes]
            ctype = response.headers.get("content-type", "").lower()
            encoding = response.encoding or "utf-8"
            status = response.status_code
    except httpx.TimeoutException:
        return Page(url, False, error="timeout")
    except httpx.HTTPError as exc:
        return Page(url, False, error=exc.__class__.__name__)
    if "pdf" in ctype:
        return Page(url, True, status, text="", error="PDF, not read", truncated=truncated)
    decoded = raw.decode(encoding, errors="replace")
    text = decoded if "text/plain" in ctype else html_to_text(decoded)
    return Page(url, True, status, text=text, truncated=truncated)


async def check_link(client: httpx.AsyncClient, url: str) -> Page:
    """HEAD, then GET when the server does not allow HEAD; no body is read."""
    try:
        response = await client.head(url)
        if response.status_code in (403, 405, 501) or response.status_code >= 500:
            async with client.stream("GET", url) as streamed:
                status = streamed.status_code
        else:
            status = response.status_code
    except httpx.TimeoutException:
        return Page(url, False, error="timeout")
    except httpx.HTTPError as exc:
        return Page(url, False, error=exc.__class__.__name__)
    if status >= 400:
        return Page(url, False, status, error=f"HTTP {status}")
    return Page(url, True, status)


async def gather_limited(coros: list[Any], limit: int = 5) -> list[Any]:
    """Run coroutines with at most `limit` at a time (polite to the source servers)."""
    sem = asyncio.Semaphore(limit)

    async def one(c: Any) -> Any:
        async with sem:
            return await c

    return await asyncio.gather(*(one(c) for c in coros))


# --- Excerpts for the model -----------------------------------------------------------------

_WORD = re.compile(r"[a-zà-ÿ0-9]{4,}")


def excerpt(text: str, focus: str, limit: int) -> str:
    """At most `limit` characters of `text`: the start of the page and the paragraphs that
    share the most words with `focus` (the question and its answer), in page order."""
    if len(text) <= limit:
        return text
    words = set(_WORD.findall(focus.lower()))
    paras = [p[:limit] for p in text.split("\n") if p.strip()]
    score = [len(words & set(_WORD.findall(p.lower()))) for p in paras]
    keep: set[int] = set()
    size = 0

    def take(i: int) -> None:
        nonlocal size
        if i not in keep and size + len(paras[i]) + 1 <= limit:
            keep.add(i)
            size += len(paras[i]) + 1

    for i in range(min(5, len(paras))):  # the start: title and first lines
        if size < limit // 4:
            take(i)
    for i in sorted(range(len(paras)), key=lambda i: -score[i]):  # the best matches
        if score[i] == 0:
            break
        take(i)
    for i in range(len(paras)):  # then the rest of the page in order, while there is room
        take(i)
    return "\n".join(paras[i] for i in sorted(keep))[:limit]

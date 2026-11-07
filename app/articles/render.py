"""A small, safe Markdown renderer for the proposal email and the review page: headings,
paragraphs, lists, GFM tables, bold, italics and links. Everything is escaped first; only
https links become anchors. Placeholders (guide:, article:, try:) are shown as marked text,
since the email and page are not the site and the site resolves them per language."""

from __future__ import annotations

import html
import re
from typing import Any

from app.articles.validate import LINK_RE

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_HEADING = re.compile(r"^(#{2,6})\s+(.*?)\s*#*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBER = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def placeholder_label(target: str) -> str:
    if target.startswith("guide:"):
        return f"guide page {target[6:]}"
    if target.startswith("article:"):
        return f"article {target[8:]}"
    if target == "try:":
        return "free practice"
    return target


def inline(text: str) -> str:
    out: list[str] = []
    pos = 0
    for m in LINK_RE.finditer(text):
        out.append(_emphasis(html.escape(text[pos : m.start()])))
        label, target = m.group(1), m.group(2)
        if target.startswith("https://"):
            out.append(
                f'<a href="{html.escape(target, quote=True)}">{_emphasis(html.escape(label))}</a>'
            )
        else:
            out.append(
                f'<span style="border-bottom:1px dashed #0E6E6B">{_emphasis(html.escape(label))}'
                f"</span>"
                f' <small style="color:#666">[{html.escape(placeholder_label(target))}]</small>'
            )
        pos = m.end()
    out.append(_emphasis(html.escape(text[pos:])))
    return "".join(out)


def _emphasis(escaped: str) -> str:
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    return _ITALIC.sub(r"<em>\1</em>", escaped)


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def markdown_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
            continue
        h = _HEADING.match(line)
        if h:
            flush()
            level = min(len(h.group(1)), 4)
            out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            head = _cells(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1
            cell = 'style="border:1px solid #ddd;padding:4px 8px;text-align:left"'
            ths = "".join(f"<th {cell}>{inline(c)}</th>" for c in head)
            trs = "".join(
                "<tr>" + "".join(f"<td {cell}>{inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            out.append(
                f'<table style="border-collapse:collapse;margin:8px 0"><tr>{ths}</tr>{trs}</table>'
            )
            continue
        for pattern, tag in ((_BULLET, "ul"), (_NUMBER, "ol")):
            if pattern.match(line):
                flush()
                items = []
                while i < len(lines) and pattern.match(lines[i]):
                    items.append(pattern.match(lines[i]).group(1))
                    i += 1
                    # continuation lines of the same item
                    while (
                        i < len(lines)
                        and lines[i].startswith("  ")
                        and lines[i].strip()
                        and not pattern.match(lines[i])
                    ):
                        items[-1] += " " + lines[i].strip()
                        i += 1
                out.append(
                    f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>"
                )
                break
        else:
            para.append(line.strip())
            i += 1
    flush()
    return "\n".join(out)


def article_html(content: dict[str, Any]) -> str:
    """The whole English version as the reader will see it, boxes included."""
    e = html.escape
    parts = [f'<h1 style="font-size:24px;margin:0 0 6px">{e(content["title"])}</h1>']
    parts.append(f'<p style="color:#555;margin:0 0 12px"><em>{e(content["description"])}</em></p>')
    summary = "".join(f"<li>{e(s)}</li>" for s in content.get("summary", []))
    parts.append(
        '<div style="background:#DCEFEC;padding:8px 14px;border-radius:6px">'
        f"<strong>In brief</strong><ul>{summary}</ul></div>"
    )
    parts.append(markdown_to_html(content.get("body", "")))
    if content.get("faq"):
        faq = "".join(f"<p><strong>{e(f['q'])}</strong><br>{e(f['a'])}</p>" for f in content["faq"])
        parts.append(f"<h2>Frequently asked questions</h2>{faq}")
    if content.get("sources"):
        src = "".join(
            f'<li><a href="{e(s["url"], quote=True)}">{e(s["title"])}</a></li>'
            for s in content["sources"]
        )
        parts.append(f"<h2>Sources</h2><ul>{src}</ul>")
    if content.get("related"):
        parts.append(
            "<p><small>Related guide pages: " + e(", ".join(content["related"])) + "</small></p>"
        )
    return "\n".join(parts)


def article_text(content: dict[str, Any]) -> str:
    """The English version as plain text for the email's text part."""
    lines = [content["title"], "", content["description"], "", "In brief:"]
    lines += [f"- {s}" for s in content.get("summary", [])]
    lines += ["", content.get("body", "").strip(), "", "Frequently asked questions:"]
    for f in content.get("faq", []):
        lines += [f"Q: {f['q']}", f"A: {f['a']}", ""]
    lines.append("Sources:")
    lines += [f"- {s['title']}: {s['url']}" for s in content.get("sources", [])]
    if content.get("related"):
        lines += ["", "Related guide pages: " + ", ".join(content["related"])]
    return "\n".join(lines)

"""Institutional terms the translator must follow (content/glossary/<lang>.yaml). The files
map a German term to its translation; joined on the German term they give, for each target
language, the English term found in the article and the term to use."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from app.content.files import content_root


@lru_cache(maxsize=16)
def _terms(lang: str) -> dict[str, dict[str, Any]]:
    path = content_root() / "glossary" / f"{lang}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for t in data.get("terms") or []:
        de = t.get("term_de") or t.get("term")
        if de and t.get("translation"):
            out[de] = t
    return out


def glossary_for(lang: str) -> list[dict[str, Any]]:
    """[{english, german, use, keep_german_in_brackets}] for translating English into `lang`."""
    english = _terms("en")
    target = _terms(lang) if lang != "de" else {}
    rows = []
    for de, en in english.items():
        if lang == "de":
            use = de
        elif de in target:
            use = target[de]["translation"]
        else:
            continue
        keep = bool(target.get(de, {}).get("keep_german")) if lang != "de" else False
        rows.append(
            {
                "english": en["translation"],
                "german": de,
                "use": use,
                "keep_german_in_brackets": keep,
            }
        )
    return rows


def clear_cache() -> None:
    _terms.cache_clear()

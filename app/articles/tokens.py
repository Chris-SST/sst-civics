"""Signed links for Chris's review page: `<article id hex>.<HMAC-SHA256>` over the article id
and its `review_nonce`, keyed with SECRET_KEY. One token per article (single-article scope),
valid while the article is unpublished and for UPDATE_WINDOW_DAYS after its latest
publication. A new nonce revokes every earlier link. Nothing is stored for the token itself."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta

from app.articles.constants import UPDATE_WINDOW_DAYS
from app.config import get_settings
from app.models import Article


def _sig(article_id: uuid.UUID, nonce: str) -> str:
    key = get_settings().secret_key.encode("utf-8")
    msg = f"viapunt-article-review|{article_id.hex}|{nonce}".encode()
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def make_token(article: Article) -> str:
    return f"{article.id.hex}.{_sig(article.id, article.review_nonce)}"


def parse_token(token: str) -> uuid.UUID | None:
    """The article id named by a well-formed token (the signature is checked by verify)."""
    head, _, sig = token.partition(".")
    if not sig or len(head) != 32 or len(token) > 120:
        return None
    try:
        return uuid.UUID(hex=head)
    except ValueError:
        return None


def verify(token: str, article: Article) -> bool:
    _, _, sig = token.partition(".")
    return hmac.compare_digest(sig, _sig(article.id, article.review_nonce))


def expired(article: Article, now: datetime) -> bool:
    if article.last_published_at is None:
        return False
    return now > article.last_published_at + timedelta(days=UPDATE_WINDOW_DAYS)


def review_url(article: Article, action: str | None = None) -> str:
    base = get_settings().app_base_url.rstrip("/")
    url = f"{base}/api/articles/review/{make_token(article)}"
    return f"{url}?action={action}" if action else url

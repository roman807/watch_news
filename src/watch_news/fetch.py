from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import Source

USER_AGENT = (
    "Mozilla/5.0 (compatible; WatchNewsDigest/1.0; "
    "+https://github.com/) personal-use RSS reader"
)
REQUEST_TIMEOUT = 15
FALLBACK_SCRAPE_LIMIT = 20


@dataclass(frozen=True)
class RawEntry:
    url: str
    title: str
    published: datetime | None
    summary: str


def fetch_entries(source: Source) -> list[RawEntry]:
    if source.feed_url:
        return _fetch_feed(source.feed_url)
    return _scrape_homepage(source.homepage)


def _fetch_feed(feed_url: str) -> list[RawEntry]:
    parsed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
    entries = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        published = _to_datetime(entry.get("published_parsed"))
        summary = _clean_summary(entry.get("summary", ""))
        entries.append(RawEntry(url=link, title=title, published=published, summary=summary))
    return entries


def _to_datetime(time_struct) -> datetime | None:
    if not time_struct:
        return None
    return datetime.fromtimestamp(calendar.timegm(time_struct), tz=timezone.utc)


def _clean_summary(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


def _scrape_homepage(homepage: str) -> list[RawEntry]:
    """Best-effort fallback for sources without a discoverable feed.

    Looks for links inside <article> elements first, then falls back to
    common blog-listing heading selectors. No per-site tuning here since
    every currently configured source has a real feed; add site-specific
    selectors if a future feed-less source needs them.
    """
    try:
        resp = requests.get(homepage, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    anchors = []
    for article in soup.find_all("article"):
        anchors.extend(article.find_all("a", href=True))
    if not anchors:
        for selector in ("h2 a[href]", "h3 a[href]", ".entry-title a[href]", ".post-title a[href]"):
            anchors.extend(soup.select(selector))

    seen_urls = set()
    entries = []
    for a in anchors:
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or not href:
            continue
        url = urljoin(homepage, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        entries.append(RawEntry(url=url, title=title, published=None, summary=""))
        if len(entries) >= FALLBACK_SCRAPE_LIMIT:
            break
    return entries

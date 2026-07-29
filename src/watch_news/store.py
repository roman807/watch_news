from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import DATA_DIR, DB_PATH

RECENT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class SeenArticle:
    url: str
    source: str
    title: str
    summary: str
    published: str | None
    first_seen: str


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_articles (
            url TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            published TEXT,
            first_seen TEXT NOT NULL
        )
        """
    )
    conn.commit()


def count_for_source(conn: sqlite3.Connection, source: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM seen_articles WHERE source = ?", (source,)
    ).fetchone()
    return row["n"]


def lookup(conn: sqlite3.Connection, url: str) -> SeenArticle | None:
    row = conn.execute(
        "SELECT * FROM seen_articles WHERE url = ?", (url,)
    ).fetchone()
    if row is None:
        return None
    return SeenArticle(
        url=row["url"],
        source=row["source"],
        title=row["title"],
        summary=row["summary"],
        published=row["published"],
        first_seen=row["first_seen"],
    )


def is_recent(article: SeenArticle, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    first_seen = datetime.fromisoformat(article.first_seen)
    return now - first_seen < RECENT_WINDOW


def upsert(
    conn: sqlite3.Connection,
    *,
    url: str,
    source: str,
    title: str,
    summary: str,
    published: str | None,
    first_seen: str,
) -> None:
    conn.execute(
        """
        INSERT INTO seen_articles (url, source, title, summary, published, first_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            published = excluded.published
        """,
        (url, source, title, summary, published, first_seen),
    )

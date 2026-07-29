from __future__ import annotations

import trafilatura

MAX_CHARS = 3000 #6000


def get_full_text(url: str) -> str | None:
    """Best-effort full-article text extraction. Returns None on any failure
    so callers can fall back to the RSS summary/description instead."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded, favor_precision=True)
    except Exception:
        return None
    if not text:
        return None
    return text[:MAX_CHARS]

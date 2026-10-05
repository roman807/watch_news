from __future__ import annotations

from .llm import Client

# Anthropic backend; the OpenAI-compatible one uses WATCH_NEWS_SUMMARY_MODEL (see llm.py).
MODEL = "claude-haiku-4-5"  #"claude-opus-5"
MAX_SUMMARY_TOKENS = 200

PROMPT_TEMPLATE = """You are writing a single entry in a daily watch-news digest.

Source: {source}
Title: {title}

Article text:
{text}

Write a concise 2-3 sentence summary for a watch collector skimming the day's \
news. Focus on the concrete news (what watch/brand/event, what's new or \
notable). No preamble, no markdown, just the summary text."""


def summarize_article(client: Client, *, source: str, title: str, text: str) -> str:
    text = text.strip() or "(no article text available, summarize from the title only)"
    return client.complete(
        "summary", MODEL, PROMPT_TEMPLATE.format(source=source, title=title, text=text), MAX_SUMMARY_TOKENS
    )


def fallback_summary(text: str, title: str) -> str:
    """Used in --dry-run mode: no API call, just trims whatever text we have."""
    text = text.strip()
    if not text:
        return title
    return text[:280] + ("…" if len(text) > 280 else "")

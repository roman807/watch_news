from __future__ import annotations

from anthropic import Anthropic

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


def summarize_article(client: Anthropic, *, source: str, title: str, text: str) -> str:
    text = text.strip() or "(no article text available, summarize from the title only)"
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_SUMMARY_TOKENS,
        messages=[
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(source=source, title=title, text=text),
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def fallback_summary(text: str, title: str) -> str:
    """Used in --dry-run mode: no API call, just trims whatever text we have."""
    text = text.strip()
    if not text:
        return title
    return text[:280] + ("…" if len(text) > 280 else "")

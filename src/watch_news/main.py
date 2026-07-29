from __future__ import annotations

import argparse
import webbrowser
from datetime import datetime, timedelta, timezone

from . import analyze, extract, fetch, store, summarize
from .config import anthropic_api_key, load_sources
from .digest import DigestItem, render_digest


def run(days: int, dry_run: bool, open_browser: bool) -> None:
    sources = load_sources()
    conn = store.get_connection()
    store.init_db(conn)

    client = None
    if not dry_run:
        api_key = anthropic_api_key()
        if not api_key:
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. Add it to .env, or pass --dry-run "
                "to test without calling the Claude API."
            )
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    grouped: dict[str, list[DigestItem]] = {}

    for source in sources:
        print(f"Fetching {source.name}...")
        entries = fetch.fetch_entries(source)

        is_first_run = store.count_for_source(conn, source.name) == 0
        if is_first_run:
            entries = entries[: source.max_initial]

        items: list[DigestItem] = []
        for entry in entries:
            if entry.published and entry.published < cutoff:
                continue

            seen = store.lookup(conn, entry.url)
            if seen is not None:
                if store.is_recent(seen, now=now):
                    items.append(
                        DigestItem(
                            title=seen.title,
                            url=seen.url,
                            summary=seen.summary,
                            published=seen.published,
                        )
                    )
                continue

            full_text = extract.get_full_text(entry.url) or entry.summary
            if dry_run:
                summary_text = summarize.fallback_summary(full_text, entry.title)
            else:
                summary_text = summarize.summarize_article(
                    client, source=source.name, title=entry.title, text=full_text
                )

            published_iso = entry.published.isoformat() if entry.published else None
            store.upsert(
                conn,
                url=entry.url,
                source=source.name,
                title=entry.title,
                summary=summary_text,
                published=published_iso,
                first_seen=now.isoformat(),
            )
            items.append(
                DigestItem(
                    title=entry.title,
                    url=entry.url,
                    summary=summary_text,
                    published=published_iso,
                )
            )

        grouped[source.name] = items
        conn.commit()

    conn.close()

    flat_items = [
        analyze.FlatItem(source=source_name, title=item.title, summary=item.summary, url=item.url)
        for source_name, source_items in grouped.items()
        for item in source_items
    ]

    if dry_run:
        digest_analysis = analyze.empty_analysis("Analysis skipped in --dry-run mode.")
    elif not flat_items:
        digest_analysis = analyze.empty_analysis("No new articles today.")
    else:
        print("Analyzing digest...")
        digest_analysis = analyze.analyze_digest(client, flat_items)

    dated_path, latest_path = render_digest(grouped, digest_analysis)
    print(f"Digest written to {dated_path}")
    if open_browser:
        webbrowser.open(f"file://{latest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a daily watch-news digest.")
    parser.add_argument(
        "--days", type=int, default=2, help="Only consider entries published within N days (default: 2)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip Anthropic API calls; use raw RSS text instead."
    )
    parser.add_argument(
        "--open", action="store_true", dest="open_browser", help="Open the digest in the default browser."
    )
    args = parser.parse_args()
    run(days=args.days, dry_run=args.dry_run, open_browser=args.open_browser)


if __name__ == "__main__":
    main()

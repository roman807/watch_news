from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import OUTPUT_DIR, TEMPLATES_DIR, load_sources


@dataclass(frozen=True)
class DigestItem:
    title: str
    url: str
    summary: str
    published: str | None


def _render_html(grouped: dict[str, list[DigestItem]], analysis, today: date, now: datetime) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("digest.html.j2")

    non_empty = {name: items for name, items in grouped.items() if items}
    total = sum(len(items) for items in non_empty.values())
    title_by_url = {item.url: item.title for items in non_empty.values() for item in items}
    source_by_url = {item.url: source for source, items in non_empty.items() for item in items}

    homepage_by_source = {s.name: s.homepage for s in load_sources()}
    source_counts = sorted(
        (
            {"name": name, "count": len(items), "homepage": homepage_by_source.get(name, "")}
            for name, items in non_empty.items()
        ),
        key=lambda sc: (-sc["count"], sc["name"].casefold()),
    )
    zero_sources = sorted(
        (
            {"name": name, "homepage": homepage_by_source.get(name, "")}
            for name, items in grouped.items()
            if not items
        ),
        key=lambda s: s["name"].casefold(),
    )

    return template.render(
        date_str=today.isoformat(),
        time_str=now.strftime("%H:%M"),
        grouped=non_empty,
        total=total,
        analysis=analysis,
        title_by_url=title_by_url,
        source_by_url=source_by_url,
        source_counts=source_counts,
        zero_sources=zero_sources,
    )


def render_digest(grouped: dict[str, list[DigestItem]], analysis, today: date | None = None) -> "tuple[str, str]":
    now = datetime.now()
    today = today or now.date()
    html = _render_html(grouped, analysis, today, now)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"{today.isoformat()}.html"
    latest_path = OUTPUT_DIR / "latest.html"
    dated_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")
    return str(dated_path), str(latest_path)


def publish_archive(
    grouped: dict[str, list[DigestItem]], analysis, publish_dir: str, today: date | None = None
) -> "tuple[str, str]":
    """Writes today's digest into publish_dir (e.g. a GitHub Pages docs/
    folder) and regenerates a chronological archive index alongside it."""
    now = datetime.now()
    today = today or now.date()
    html = _render_html(grouped, analysis, today, now)

    out_dir = Path(publish_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").touch(exist_ok=True)

    dated_path = out_dir / f"{today.isoformat()}.html"
    dated_path.write_text(html, encoding="utf-8")
    (out_dir / "latest.html").write_text(html, encoding="utf-8")

    index_path = _build_archive_index(out_dir)
    return str(dated_path), str(index_path)


def _build_archive_index(publish_dir: Path) -> Path:
    entries = []
    for path in sorted(publish_dir.glob("*.html"), reverse=True):
        if path.stem in ("index", "latest"):
            continue
        try:
            entry_date = datetime.strptime(path.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        entries.append({"filename": path.name, "display": entry_date.strftime("%A, %B %-d, %Y")})

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("archive_index.html.j2")
    html = template.render(entries=entries)

    index_path = publish_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path

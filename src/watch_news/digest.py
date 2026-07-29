from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from jinja2 import Environment, FileSystemLoader

from .config import OUTPUT_DIR, TEMPLATES_DIR


@dataclass(frozen=True)
class DigestItem:
    title: str
    url: str
    summary: str
    published: str | None


def render_digest(grouped: dict[str, list[DigestItem]], analysis, today: date | None = None) -> "tuple[str, str]":
    now = datetime.now()
    today = today or now.date()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("digest.html.j2")

    non_empty = {name: items for name, items in grouped.items() if items}
    total = sum(len(items) for items in non_empty.values())
    title_by_url = {item.url: item.title for items in non_empty.values() for item in items}
    html = template.render(
        date_str=today.isoformat(),
        time_str=now.strftime("%H:%M"),
        grouped=non_empty,
        total=total,
        analysis=analysis,
        title_by_url=title_by_url,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"{today.isoformat()}.html"
    latest_path = OUTPUT_DIR / "latest.html"
    dated_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")
    return str(dated_path), str(latest_path)

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
DB_PATH = DATA_DIR / "seen.db"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Source:
    name: str
    homepage: str
    feed_url: str | None
    max_initial: int


def load_sources() -> list[Source]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    return [
        Source(
            name=item["name"],
            homepage=item["homepage"],
            feed_url=item.get("feed_url") or None,
            max_initial=int(item.get("max_initial", 10)),
        )
        for item in raw
    ]


def anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")

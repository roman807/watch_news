from __future__ import annotations

from dataclasses import dataclass, field

from anthropic import Anthropic

MODEL = "claude-opus-5"
# Structured output across a full day's articles (summary + microbrands + new
# releases with specs + every brand discussed) plus Opus 5's default adaptive
# thinking can add up to well more than the prior 8192 cap, which was silently
# truncating whichever field the model generated last. Streaming is required
# by the SDK once max_tokens goes this high.
MAX_TOKENS = 32000
TOOL_NAME = "submit_digest_analysis"
SUMMARY_MAX_TOTAL_WORDS = 100
SUMMARY_MAX_URLS_PER_BULLET = 3

_MICROBRAND_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "note": {"type": "string", "description": "Optional short note, empty string if none."},
        "urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand", "model", "note", "urls"],
    "additionalProperties": False,
}

_BRAND_DISCUSSED_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "models": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Distinct model names discussed for this brand today; empty array if only brand-level news.",
        },
        "urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand", "models", "urls"],
    "additionalProperties": False,
}

_RELEASE_SPECS_SCHEMA = {
    "type": "object",
    "properties": {
        "size": {
            "type": "string",
            "description": "Case size/dimensions, e.g. '39mm'. Empty string if not stated in the article.",
        },
        "movement": {
            "type": "string",
            "description": "Movement/caliber, e.g. 'Automatic, Cal. 3235'. Empty string if not stated.",
        },
        "water_resistance": {
            "type": "string",
            "description": "e.g. '100m / 10 bar'. Empty string if not stated.",
        },
        "case_material": {
            "type": "string",
            "description": "e.g. 'Stainless steel', 'Titanium'. Empty string if not stated.",
        },
        "notable_features": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Other standout specs worth calling out (e.g. an unusual complication or feature). "
                "Empty array if none stand out."
            ),
        },
        "price": {
            "type": "string",
            "description": "Price as stated in the article. Empty string if not stated.",
        },
    },
    "required": ["size", "movement", "water_resistance", "case_material", "notable_features", "price"],
    "additionalProperties": False,
}

_NEW_RELEASE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "urls": {"type": "array", "items": {"type": "string"}},
        "specs": _RELEASE_SPECS_SCHEMA,
    },
    "required": ["brand", "model", "urls", "specs"],
    "additionalProperties": False,
}

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Submit the structured cross-article analysis of today's watch-news digest.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary_bullets": {
                "type": "array",
                "description": (
                    f"3 to 6 concise bullet points covering what stands out today across all "
                    f"sources combined — e.g. watches/brands covered by multiple outlets, major "
                    f"releases from big brands, surprising new complications or breakthroughs, "
                    f"notable pieces by well-known journalists (Ben Clymer, Wei Koh, Jack "
                    f"Forster), etc. Keep the combined bullets short — well under "
                    f"{SUMMARY_MAX_TOTAL_WORDS} words total across all of them."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The bullet point itself — one concise sentence.",
                        },
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "1 to 3 urls (from the article list below) that this bullet is "
                                "based on."
                            ),
                        },
                    },
                    "required": ["text", "urls"],
                    "additionalProperties": False,
                },
            },
            "microbrands": {
                "type": "array",
                "description": (
                    "Articles discussing microbrands: independent/smaller brands, typically in "
                    "the $500-$3,000 range."
                ),
                "items": _MICROBRAND_ITEM_SCHEMA,
            },
            "new_releases": {
                "type": "array",
                "description": (
                    "Newly announced/released models today, one entry per brand+model, with "
                    "article links and key specs pulled from the article."
                ),
                "items": _NEW_RELEASE_ITEM_SCHEMA,
            },
            "brands_discussed": {
                "type": "array",
                "description": (
                    "Every distinct brand discussed today — one entry per brand, not per model — "
                    "with the model(s) discussed and all article urls. This is typically the "
                    "longest list of the four — generate it last so the shorter, higher-value "
                    "sections above are never cut short."
                ),
                "items": _BRAND_DISCUSSED_ITEM_SCHEMA,
            },
        },
        "required": ["summary_bullets", "microbrands", "new_releases", "brands_discussed"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass(frozen=True)
class FlatItem:
    source: str
    title: str
    summary: str
    url: str


@dataclass(frozen=True)
class BrandGroup:
    brand: str
    model: str
    urls: list = field(default_factory=list)
    note: str = ""
    sources: list = field(default_factory=list)


@dataclass(frozen=True)
class BrandDiscussed:
    brand: str
    models: list
    urls: list
    sources: list


@dataclass(frozen=True)
class ReleaseSpecs:
    size: str = ""
    movement: str = ""
    water_resistance: str = ""
    case_material: str = ""
    notable_features: list = field(default_factory=list)
    price: str = ""


@dataclass(frozen=True)
class NewRelease:
    brand: str
    model: str
    urls: list
    specs: ReleaseSpecs
    sources: list = field(default_factory=list)


@dataclass(frozen=True)
class SummaryBullet:
    text: str
    urls: list = field(default_factory=list)


@dataclass(frozen=True)
class DigestAnalysis:
    summary_bullets: list
    microbrands: list
    brands_discussed: list
    new_releases: list


def empty_analysis(note: str = "") -> DigestAnalysis:
    bullets = [SummaryBullet(text=note, urls=[])] if note else []
    return DigestAnalysis(summary_bullets=bullets, microbrands=[], brands_discussed=[], new_releases=[])


def _process_summary_bullets(raw_bullets: list, valid_urls: set) -> list:
    bullets = []
    remaining_words = SUMMARY_MAX_TOTAL_WORDS
    for entry in raw_bullets:
        if remaining_words <= 0:
            break
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        words = text.split()
        if len(words) > remaining_words:
            text = " ".join(words[:remaining_words]) + "…"
            words = words[:remaining_words]
        remaining_words -= len(words)

        seen_urls = []
        for u in entry.get("urls", []):
            if u in valid_urls and u not in seen_urls:
                seen_urls.append(u)
        urls = seen_urls[:SUMMARY_MAX_URLS_PER_BULLET]

        bullets.append(SummaryBullet(text=text, urls=urls))
    return bullets


def _merge_microbrands(raw_groups: list, valid_urls: set, url_to_source: dict) -> list:
    merged: dict = {}
    for entry in raw_groups:
        brand = (entry.get("brand") or "").strip()
        model = (entry.get("model") or "").strip()
        note = (entry.get("note") or "").strip()
        urls = [u for u in entry.get("urls", []) if u in valid_urls]
        if not brand or not urls:
            continue
        key = (brand.casefold(), model.casefold())
        if key in merged:
            e_brand, e_model, e_urls, e_note = merged[key]
            merged[key] = (e_brand, e_model, list(dict.fromkeys(e_urls + urls)), e_note or note)
        else:
            merged[key] = (brand, model, urls, note)

    result = [
        BrandGroup(
            brand=b,
            model=m,
            urls=u,
            note=n,
            sources=sorted({url_to_source[url] for url in u if url in url_to_source}, key=str.casefold),
        )
        for (b, m, u, n) in merged.values()
    ]
    return sorted(result, key=lambda g: (g.brand.casefold(), g.model.casefold()))


def _merge_brands_discussed(raw_groups: list, valid_urls: set, url_to_source: dict) -> list:
    merged: dict = {}
    for entry in raw_groups:
        brand = (entry.get("brand") or "").strip()
        models = [m.strip() for m in entry.get("models", []) if m and m.strip()]
        urls = [u for u in entry.get("urls", []) if u in valid_urls]
        if not brand or not urls:
            continue
        key = brand.casefold()
        if key in merged:
            existing = merged[key]
            merged[key] = {
                "brand": existing["brand"],
                "models": list(dict.fromkeys(existing["models"] + models)),
                "urls": list(dict.fromkeys(existing["urls"] + urls)),
            }
        else:
            merged[key] = {"brand": brand, "models": models, "urls": urls}

    result = []
    for entry in merged.values():
        sources = sorted({url_to_source[u] for u in entry["urls"] if u in url_to_source}, key=str.casefold)
        models_sorted = sorted(dict.fromkeys(entry["models"]), key=str.casefold)
        result.append(BrandDiscussed(brand=entry["brand"], models=models_sorted, urls=entry["urls"], sources=sources))
    return sorted(result, key=lambda b: b.brand.casefold())


def _merge_new_releases(raw_groups: list, valid_urls: set, url_to_source: dict) -> list:
    merged: dict = {}
    for entry in raw_groups:
        brand = (entry.get("brand") or "").strip()
        model = (entry.get("model") or "").strip()
        urls = [u for u in entry.get("urls", []) if u in valid_urls]
        if not brand or not urls:
            continue

        raw_specs = entry.get("specs") or {}
        specs = ReleaseSpecs(
            size=(raw_specs.get("size") or "").strip(),
            movement=(raw_specs.get("movement") or "").strip(),
            water_resistance=(raw_specs.get("water_resistance") or "").strip(),
            case_material=(raw_specs.get("case_material") or "").strip(),
            notable_features=[f.strip() for f in raw_specs.get("notable_features", []) if f and f.strip()],
            price=(raw_specs.get("price") or "").strip(),
        )

        key = (brand.casefold(), model.casefold())
        if key in merged:
            e_brand, e_model, e_urls, e_specs = merged[key]
            merged[key] = (
                e_brand,
                e_model,
                list(dict.fromkeys(e_urls + urls)),
                ReleaseSpecs(
                    size=e_specs.size or specs.size,
                    movement=e_specs.movement or specs.movement,
                    water_resistance=e_specs.water_resistance or specs.water_resistance,
                    case_material=e_specs.case_material or specs.case_material,
                    notable_features=list(dict.fromkeys(e_specs.notable_features + specs.notable_features)),
                    price=e_specs.price or specs.price,
                ),
            )
        else:
            merged[key] = (brand, model, urls, specs)

    result = [
        NewRelease(
            brand=b,
            model=m,
            urls=u,
            specs=s,
            sources=sorted({url_to_source[url] for url in u if url in url_to_source}, key=str.casefold),
        )
        for (b, m, u, s) in merged.values()
    ]
    return sorted(result, key=lambda r: (r.brand.casefold(), r.model.casefold()))


def analyze_digest(client: Anthropic, items: list) -> DigestAnalysis:
    if not items:
        return empty_analysis("No new articles today.")

    valid_urls = {item.url for item in items}
    url_to_source = {item.url: item.source for item in items}
    listing = "\n".join(
        f"- source: {item.source} | title: {item.title} | url: {item.url}\n  summary: {item.summary}"
        for item in items
    )

    prompt = f"""Here are today's watch-news articles (source, title, url, summary):

{listing}

Analyze these as a set and call {TOOL_NAME}. Only use urls that appear in the article list above — never invent one."""

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    tool_use = next(b for b in response.content if b.type == "tool_use")
    data = tool_use.input

    return DigestAnalysis(
        summary_bullets=_process_summary_bullets(data.get("summary_bullets", []), valid_urls),
        microbrands=_merge_microbrands(data.get("microbrands", []), valid_urls, url_to_source),
        brands_discussed=_merge_brands_discussed(data.get("brands_discussed", []), valid_urls, url_to_source),
        new_releases=_merge_new_releases(data.get("new_releases", []), valid_urls, url_to_source),
    )

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

# Non-exhaustive seed list of independent watch brands (upper luxury segment,
# not owned by a major group/conglomerate). Passed to the model as a strong
# prior in the prompt; it's expected to extend this using its own judgment
# per the definition in the "independents" schema field below.
KNOWN_INDEPENDENT_BRANDS = [
    "Otsuka Lotec", "Reservoir", "RGM Watch Co", "Zeitwinkel", "Akrivia",
    "Armando Legin", "Andersen Genève", "Andreas Strehler", "Armin Strom",
    "Artime Creations", "ArtyA", "Berneron", "Bianchet", "Biver", "Bovet",
    "Charles Frodsham", "Christian Klings", "Christian vaan der Klaauw",
    "Christophe Claret", "Cyrus", "Czapek", "Dominique Renaud", "Fam Al Hut",
    "Felipe Pikullik", "Fleming", "F.P. Journe", "Franck Muller",
    "Gerald Charles", "Greubel Forsey", "Hautlence", "H. Moser & Cie.",
    "Hysek", "HYT", "J.N. Shapiro", "Jacob & Co.", "Konstantin Chaykin",
    "Krayon", "Laurent Ferrier", "Lederer", "Linde Werdelin", "Lorige",
    "Louis Moinet", "Luca Soprana", "Marco Lang", "Mauron Musy", "MB&F",
    "Moritz Grossmann", "Naoya Hida & Co", "Parmigiani Fleurier",
    "Petermann Bédat", "Purnell", "Qian GuoBiao", "Rebellion", "Rémy Cools",
    "Ressence", "Roger W. Smith", "Romain Gauthier", "Sylvain Pinaud",
    "Simon Brette", "Ulysse Nardin", "Urban Jürgensen", "Urwerk", "Vanguart",
    "Vault", "Vianney Halter", "Voutilainen",
]

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
        "urls": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Only urls of articles that are dedicated to this brand, or that give it a "
                "substantial standalone section (e.g. its own entry in a multi-brand roundup). "
                "Do not include an article just because the brand is namedropped or compared "
                "in passing."
            ),
        },
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

_BUSINESS_NEWS_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "description": "A short label for this business-news item, e.g. 'LVMH H1 2026 results' or 'Windup Chicago attendance record'.",
        },
        "summary": {
            "type": "string",
            "description": "One quick sentence summarizing the news.",
        },
        "urls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Urls covering this story; merge multiple outlets covering the same story into one entry.",
        },
    },
    "required": ["topic", "summary", "urls"],
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
            "independents": {
                "type": "array",
                "description": (
                    "Independent watch brands in the upper luxury segment — not owned by a "
                    "major group/conglomerate (e.g. LVMH, Richemont, Swatch Group, Kering) — "
                    "typically $10,000+ and mostly $50,000+. A non-exhaustive list of known "
                    "independent brands is given in the prompt as a strong prior; also classify "
                    "other brands into this category using your own knowledge when they fit the "
                    "definition (small, independently owned, high price tier). Do not include a "
                    "brand here if it's already a microbrand above."
                ),
                "items": _MICROBRAND_ITEM_SCHEMA,
            },
            "new_releases": {
                "type": "array",
                "description": (
                    "Newly announced/released models — only include an article if it frames "
                    "the watch as a new announcement (e.g. 'Introducing', 'announces', "
                    "'unveils', 'debut', 'coming soon'). Exclude articles framed as a "
                    "retrospective/review of an already-released watch (e.g. 'Hands-On', "
                    "'Owner's Review'). Do not use the presence or absence of full specs as a "
                    "signal either way — a genuine new-release announcement often also gives "
                    "full specs. One entry per brand+model, with article links and key specs "
                    "pulled from the article."
                ),
                "items": _NEW_RELEASE_ITEM_SCHEMA,
            },
            "business_news": {
                "type": "array",
                "description": (
                    "Articles about the watch business/industry rather than a specific watch — "
                    "e.g. brand or group financial results, executive moves, acquisitions, "
                    "retail or export data, trade-show attendance figures, industry trends. One "
                    "entry per distinct story; merge multiple outlets covering the same story "
                    "into a single entry with all their urls. Empty array if there's no business "
                    "news today."
                ),
                "items": _BUSINESS_NEWS_ITEM_SCHEMA,
            },
            "brands_discussed": {
                "type": "array",
                "description": (
                    "Mainstream/established brands that get substantive coverage today — one "
                    "entry per brand, not per model — with the model(s) discussed and the "
                    "article urls that back it. Do NOT include a brand here if it's a microbrand "
                    "or an independent already captured in the lists above — this list is for "
                    "everything else, and each brand should appear in exactly one of the three "
                    "lists. Inclusion bar: only include a brand if at least one article is "
                    "dedicated to it, or gives it a whole standalone section within an article "
                    "covering multiple brands/models (e.g. one write-up in a roundup, one item in "
                    "a 'top 5 watches' list). Do NOT include a brand solely because it's "
                    "namedropped, mentioned in a one-line comparison, or referenced in passing "
                    "inside an article that isn't substantially about it. When in doubt, leave it "
                    "out. This is typically the longest list of the four — generate it last so "
                    "the shorter, higher-value sections above are never cut short."
                ),
                "items": _BRAND_DISCUSSED_ITEM_SCHEMA,
            },
        },
        "required": [
            "summary_bullets",
            "microbrands",
            "independents",
            "new_releases",
            "business_news",
            "brands_discussed",
        ],
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
class BusinessNewsItem:
    topic: str
    summary: str
    urls: list = field(default_factory=list)
    sources: list = field(default_factory=list)


@dataclass(frozen=True)
class DigestAnalysis:
    summary_bullets: list
    microbrands: list
    independents: list
    brands_discussed: list
    new_releases: list
    business_news: list


def empty_analysis(note: str = "") -> DigestAnalysis:
    bullets = [SummaryBullet(text=note, urls=[])] if note else []
    return DigestAnalysis(
        summary_bullets=bullets,
        microbrands=[],
        independents=[],
        brands_discussed=[],
        new_releases=[],
        business_news=[],
    )


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


def _merge_brand_groups(raw_groups: list, valid_urls: set, url_to_source: dict) -> list:
    """Shared brand+model+note+urls merge, used for both Microbrands and Independents."""
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


def _merge_business_news(raw_items: list, valid_urls: set, url_to_source: dict) -> list:
    merged: dict = {}
    order: list = []
    for entry in raw_items:
        topic = (entry.get("topic") or "").strip()
        summary = (entry.get("summary") or "").strip()
        urls = [u for u in entry.get("urls", []) if u in valid_urls]
        if not topic or not urls:
            continue
        key = topic.casefold()
        if key in merged:
            e_topic, e_summary, e_urls = merged[key]
            merged[key] = (e_topic, e_summary or summary, list(dict.fromkeys(e_urls + urls)))
        else:
            merged[key] = (topic, summary, urls)
            order.append(key)

    result = []
    for key in order:
        topic, summary, urls = merged[key]
        sources = sorted({url_to_source[u] for u in urls if u in url_to_source}, key=str.casefold)
        result.append(BusinessNewsItem(topic=topic, summary=summary, urls=urls, sources=sources))
    return result


def analyze_digest(client: Anthropic, items: list) -> DigestAnalysis:
    if not items:
        return empty_analysis("No new articles today.")

    valid_urls = {item.url for item in items}
    url_to_source = {item.url: item.source for item in items}
    listing = "\n".join(
        f"- source: {item.source} | title: {item.title} | url: {item.url}\n  summary: {item.summary}"
        for item in items
    )

    known_independents = ", ".join(KNOWN_INDEPENDENT_BRANDS)

    prompt = f"""Here are today's watch-news articles (source, title, url, summary):

{listing}

Known independent brands (non-exhaustive — use as a strong prior for the "independents" \
field, and also classify other brands into it using your own judgment when they fit the \
definition given there): {known_independents}

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

    microbrands = _merge_brand_groups(data.get("microbrands", []), valid_urls, url_to_source)
    independents = _merge_brand_groups(data.get("independents", []), valid_urls, url_to_source)

    # A brand should appear in exactly one of the three brand sections. Microbrand
    # ($500-3,000) and Independent ($10k+) are mutually exclusive by definition, but
    # the model can still occasionally misclassify the same brand into both lists —
    # Independents wins ties since it's the narrower, more specific bar.
    independent_names = {g.brand.casefold() for g in independents}
    microbrands = [g for g in microbrands if g.brand.casefold() not in independent_names]

    exclusive_names = {g.brand.casefold() for g in microbrands} | independent_names

    brands_discussed = _merge_brands_discussed(data.get("brands_discussed", []), valid_urls, url_to_source)
    # "Mainstream Brands" is defined as brands NOT already covered in Microbrands or
    # Independents — enforced here rather than trusted from the model, same as url
    # validation above.
    brands_discussed = [b for b in brands_discussed if b.brand.casefold() not in exclusive_names]

    return DigestAnalysis(
        summary_bullets=_process_summary_bullets(data.get("summary_bullets", []), valid_urls),
        microbrands=microbrands,
        independents=independents,
        brands_discussed=brands_discussed,
        new_releases=_merge_new_releases(data.get("new_releases", []), valid_urls, url_to_source),
        business_news=_merge_business_news(data.get("business_news", []), valid_urls, url_to_source),
    )

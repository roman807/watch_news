# Watch News Digest

Pulls new articles from a configurable list of watch-news sites, summarizes
each one with the Claude API, and writes a daily HTML digest you can open
in your browser.

The digest has five sections, navigable via a sidebar: a bullet-point
**Summary** of what stands out (watches covered by multiple sources, major
brand releases, notable journalists, etc.), **Microbrands** (independent
brands roughly $500-$3,000), **Mainstream Brands** (every other brand + model
mentioned, alphabetized, with all its article links and covering outlets
merged into one entry), **New Releases** (same, for newly announced models,
plus key specs), and **Business News** (industry/financial stories). The same
article commonly appears in several sections — that's expected.

Per-article summaries and the cross-article analysis both use
`claude-opus-5`. If you want to cut cost on the per-article pass (it runs
once per new article), swap the `MODEL` constant in `summarize.py` for
`claude-haiku-4-5` — the cross-article analysis in `analyze.py` benefits
more from Opus-tier reasoning (brand/microbrand classification, merging
duplicate mentions) so it's worth keeping as-is.

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

## Run

```bash
./venv/bin/python -m watch_news.main --open
```

- `--dry-run` — skip Claude API calls and use the raw RSS text instead (good
  for testing config/scraping changes for free).
- `--days N` — only consider articles published within the last N days
  (default 2).
- `--open` — open the generated digest in your default browser when done.
- `--publish-dir DIR` — also write the digest and a regenerated chronological
  archive index into `DIR` (see "Automated daily runs" below).

Output is written to `output/<YYYY-MM-DD>.html` and `output/latest.html`.

## How dedup works

Every article URL is recorded in `data/seen.db` (SQLite) the first time it's
processed, along with its summary. On later runs:

- Articles not seen before are fetched, summarized, and added.
- Articles first seen **less than 24 hours ago** are still included in the
  digest (using the cached summary, no extra API call) — so running the
  script multiple times in one day keeps showing that day's news.
- Articles first seen **24+ hours ago** are skipped, since they've already
  been surfaced.

The very first time a source is added, only its `max_initial` most recent
entries are summarized (see `config/sources.yaml`), to avoid processing an
entire feed's history — and cost — on day one.

## Adding a source

Edit `config/sources.yaml`:

```yaml
- name: Some Site
  homepage: https://example.com/
  feed_url: https://example.com/feed   # RSS/Atom feed if it has one
  max_initial: 10
```

If a site has no discoverable feed, omit `feed_url` and it will fall back to
a generic scrape of `homepage` (looks for links inside `<article>` tags,
then common heading selectors). This fallback is best-effort — sites with
unusual markup may need custom selectors added to `fetch.py`.

## Automated daily runs + GitHub Pages archive

`.github/workflows/daily-digest.yml` runs the digest automatically once a
day at 6pm Central European time (both CET and CEST are handled — GitHub
Actions cron is UTC-only and doesn't shift for daylight saving, so the
workflow schedules both UTC offsets and a guard step picks the correct one)
and publishes it to a GitHub Pages site with a chronological archive
(newest first) as the homepage.

One-time setup:

1. **Add your API key as a repo secret**: repo Settings → Secrets and
   variables → Actions → New repository secret → name it
   `ANTHROPIC_API_KEY`.
2. **Enable Pages**: repo Settings → Pages → Source: "Deploy from a branch"
   → Branch `main`, folder `/docs` → Save. It's fine to do this before
   `docs/` has any content.
3. Either wait for the next scheduled run, or trigger it immediately from
   the Actions tab → "Daily Watch News Digest" → "Run workflow" (this spends
   real API credit, same as any real run).

Each run commits `data/seen.db` (the dedup state — no longer gitignored, so
it persists across the ephemeral GitHub Actions runners) and `docs/` (the
published HTML) back to the repo.

Prefer to run it yourself instead? A local cron entry or macOS `launchd` job
running `/full/path/to/watch_news/venv/bin/python -m watch_news.main` works
the same way — just skip the GitHub Actions setup above.

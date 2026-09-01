# Jury instructions

Everything needed to run and check this submission, on a clean machine, in one command.

## Run it

```bash
./run-jury.sh https://example.com
```

That creates a virtualenv, installs dependencies, runs the full test suite, and audits the URL,
writing `audit-report.json` and printing a summary. No API key, no account, no external service.

If you prefer to drive it yourself:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/python -m brand_ai_readiness https://example.com -o audit-report.json
```

Browser rendering is optional. Without Playwright installed the audit still completes and reports
`rendering_status: "unavailable"` rather than silently under-reporting. To enable it:

```bash
./.venv/bin/pip install playwright && ./.venv/bin/playwright install chromium
```

## What to expect

| | |
|---|---|
| Runtime | 3–90s for a typical site (budget is 5 minutes); dominated by network, not CPU |
| Default budget | 40 pages, 8 rendered, concurrency 4, 15s timeout, 2 MB per response |
| Network | GET and HEAD only, enforced in code (`SAFE_METHODS`); non-read methods raise |
| Output | One JSON object: `site`, `audited_at`, `summary`, `findings[]`, plus `coverage`, `scores`, `proactive_recommendations` |
| Tests | `./.venv/bin/python -m pytest -q` — 133 passing, 1 skipped (a live-network test, opt-in) |

## Verify the marketplace

```bash
npx skills-ref@latest validate ./skills/audit-orchestrator   # and each other skill
./.venv/bin/python skills/audit-orchestrator/scripts/validate_report.py audit-report.json
./.venv/bin/python scripts/package_zip.py                    # builds the submission zip
```

`marketplace.json` lists five skills with exactly one entrypoint (`audit-orchestrator`). Each skill
folder holds its own `SKILL.md`, `scripts/` and `references/`.

## Run one skill in isolation

Each sub-skill's scripts run standalone, which is the quickest way to inspect a single concern:

```bash
./.venv/bin/python skills/crawl-render-audit/scripts/access_probe.py https://example.com
./.venv/bin/python skills/crawl-render-audit/scripts/crawler.py https://example.com --max-pages 5
./.venv/bin/python skills/structured-data-audit/scripts/jsonld.py https://example.com
```

## Known limitations

Stated plainly, because a report that hides them is worth less than one that does not.

- **Corroboration is not performed.** Checking whether a claim is repeated on independent domains
  needs a web-search tool the audit does not assume. `corroboration_status` is `unavailable` by
  default and no finding ever asserts a claim is false.
- **Without Playwright, raw-vs-rendered gaps are under-counted.** Reported in
  `coverage.limitations` rather than passed over.
- **Findings are scoped to what was crawled.** Evidence is phrased "0/N crawled pages", never "the
  site has none anywhere". The crawl budget appears in `coverage`.
- **The access probe needs a reachable origin.** If a site refuses the browser identity too
  (paywall, geo-block, rate limit) the probe reports `partial` and emits nothing, rather than
  guessing. Sites that rate-limit under repeated auditing can land here.
- **On-page auditing has a ceiling.** The factors correlating most strongly with AI citation are
  off-site — branded mentions across the web, third-party coverage — and no on-page tool can move
  them. `proactive_recommendations` says where on-page work stops helping.
- **Site-type inference is a heuristic.** It reports `mixed` rather than committing when signals
  are close, because a confident wrong type produces a confident wrong recommendation.
- **`llms.txt` is deliberately not checked.** In a 137k-domain study, 97% of published `llms.txt`
  files received zero requests in a month and AI crawlers never went looking for absent ones.
  Reporting it would add a finding with no mechanism behind it.

## Design decisions worth knowing

- **Severity is arithmetic, never a model's opinion** — `impact_weight × scope × confidence` in
  `scoring/severity.py`. An optional `--llm-polish` flag can reword `suggested_action.details` if
  `OPENAI_API_KEY` is set; it is off by default, touches no other field, and cannot alter severity.
- **Only AI *search* crawlers can raise a finding.** `GPTBot` and `ClaudeBot` are training
  crawlers; blocking them while allowing `OAI-SearchBot` is a supported configuration, not a
  defect, so it is recorded as context instead.
- **Absence of a signal is not proof of intent.** When robots.txt cannot be read, the audit says so
  rather than treating the parser's permissive default as permission.

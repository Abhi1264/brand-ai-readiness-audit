---
name: audit-orchestrator
description: Compose crawl, AI-crawler access, structured-data, freshness/entity, and engagement audits into one validated report of AI-discoverability and on-site-engagement findings. Use when asked to audit a website URL, diagnose why a brand is missing or misrepresented in AI assistants, or produce prioritized fix recommendations. Recommend-only; never modify the live site.
license: MIT
compatibility: Requires Python 3.11+ and network GET/HEAD access to the target origin. Playwright optional. No API key required. Skill scripts import the marketplace's brand_ai_readiness package - run `pip install -e .` from the marketplace root, or run from a checkout that contains src/.
metadata:
  author: brand-ai-readiness-audit
  version: "1.0.0"
  role: entrypoint
allowed-tools: Read Bash
---

# Audit orchestrator (entrypoint)

## When to use

Use this skill when the user provides a website URL and wants a structured audit of:

- why AI assistants may fail to discover, read, trust, or cite the brand
- why a human visitor who arrives may fail to orient, continue, or convert

This skill is the marketplace entrypoint. It composes the other four skills. It does not re-implement their checks.

## Inputs

- `url` (required): public `http` or `https` website
- optional budgets: `--max-pages`, `--max-renders`, `--timeout`, `--concurrency`, `--no-render`

## Procedure

1. Confirm the request is recommend-only. Never POST/PUT/PATCH/DELETE, never submit forms, never log in, never bypass robots.txt.
2. Run the shared crawler once (`skills/audit-orchestrator/scripts/run_audit.py <url>` or `python -m brand_ai_readiness <url>`). The crawler is implemented by crawl-render-audit and reused.
3. Let crawl-render-audit produce reachability, robots, AI-crawler access (what the origin serves GPTBot/ClaudeBot/PerplexityBot vs a browser), HTTP, canonical, raw-vs-rendered, and machine-readability evidence.
4. Let structured-data-audit infer site type and compare JSON-LD / Open Graph to visible content.
5. Let freshness-entity-audit extract entities, claims, and freshness signals. If external search is not available, set `corroboration_status=unavailable` and do not invent corroboration.
6. Let engagement-audit evaluate homepage orientation, navigation, continuation, dead ends, and measurable mobile issues.
7. Normalize findings. Deduplicate by `mechanism_code` and overlapping `source_urls`.
8. Assign severity from impact × scope × confidence (deterministic). Sort so the first finding is the first fix.
9. Add contextual proactive recommendations only when they fit the inferred site type.
10. Validate the JSON with Pydantic (`scripts/validate_report.py`) before emitting it.

Read [references/orchestration.md](references/orchestration.md) for composition rules and the false-positive checklist.

## Output

A single JSON object with at least:

- `site`, `audited_at`
- `summary.total_findings`, `summary.critical`, `summary.high`, `summary.medium`
- `findings[]` each with `id`, `title`, `severity`, `evidence`, `suggested_action`

Do not claim site-wide absence of a signal unless the crawl actually covered it. Say "0/N crawled pages…" instead of "the website has none anywhere."

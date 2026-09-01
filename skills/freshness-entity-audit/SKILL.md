---
name: freshness-entity-audit
description: Extract organizations, products, and factual claims from a website and check whether names are consistent, entities are disambiguated, and time-sensitive pages have real freshness signals. Use when auditing stale content, entity ambiguity, or uncorroborated claims. Never fabricate claims or treat missing search as proof a claim is false.
license: MIT
compatibility: Requires Python 3.11+. External corroboration is optional and off by default. Skill scripts import the marketplace's brand_ai_readiness package - run `pip install -e .` from the marketplace root, or run from a checkout that contains src/.
metadata:
  author: brand-ai-readiness-audit
  version: "1.0.0"
allowed-tools: Read Bash
---

# Freshness and entity audit

## When to use

Use this skill to answer: **Are important facts current, unambiguous, internally consistent, and (when possible) independently supported?**

## Inputs

- Crawl snapshot JSON, or individual HTML files for date extraction

## Procedure

1. Extract entities from JSON-LD names, `og:site_name`, title fragments, and product titles (`scripts/entities.py`).
2. Detect inconsistent official names (more than compatible Inc/LLC suffixes).
3. Report entity ambiguity only when the site's own signals are thin: short generic name without industry + place + legal form + sameAs.
4. Extract claims that literally appear in text (`scripts/claims.py`). Each claim keeps `source_url`, `evidence_text`, and `importance`. Never invent a claim.
5. Collect freshness with `scripts/dates.py`. Distinguish `datePublished` / `dateModified` / visible "Updated" from copyright year.
6. If a page has no date, say **freshness cannot be established**. Do not call it stale.
7. Flag stale only when an explicit old date is paired with time-sensitive language (pricing, current, latest).
8. Corroboration is optional. Default `corroboration_status=unavailable`. Do not pretend a search happened.

Details: [references/entity-checks.md](references/entity-checks.md), [references/freshness-checks.md](references/freshness-checks.md).

## Output

Findings in category `entity` or `freshness`. Claims stay on the snapshot for the orchestrator; they are not fabricated evidence.

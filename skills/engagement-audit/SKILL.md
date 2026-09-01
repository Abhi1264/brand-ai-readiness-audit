---
name: engagement-audit
description: Evaluate whether a first-time visitor can tell who the site is, what it offers, who it is for, and what to do next. Checks homepage orientation, navigation labels, internal links, dead ends, broken paths, context retention on deep pages, and measurable mobile blockers. Use when auditing on-site engagement. Evidence only; no aesthetic opinions.
license: MIT
compatibility: Requires Python 3.11+. Mobile checks need Playwright when available. Skill scripts import the marketplace's brand_ai_readiness package - run `pip install -e .` from the marketplace root, or run from a checkout that contains src/.
metadata:
  author: brand-ai-readiness-audit
  version: "1.0.0"
allowed-tools: Read Bash
---

# Engagement audit

## When to use

Use this skill to answer: **Once a human arrives, can they understand the site, find the next useful action, and continue?**

## Inputs

- Crawl snapshot (preferred) or homepage HTML

## Procedure

1. On the homepage, measure H1, identity phrasing, audience phrasing, CTA phrasing, and word count (`scripts/page_analysis.py`).
2. Inspect navigation labels (`scripts/navigation.py`). Flag only generic labels ("click here", "home", "link").
3. Extract internal links (`scripts/links.py`). Dead end = product/service/article/docs page with ≤1 internal link.
4. Broken continuation = crawled href that returned 404/410.
5. If the site has pricing/product/contact pages, check that the homepage actually links to them when that path fits the inferred type.
6. Deep pages should retain brand, breadcrumb, or a path home.
7. Mobile: report only overflow, missing nav, vanished CTA, or tiny text — never pixel-perfect design critique.

Details: [references/engagement-checks.md](references/engagement-checks.md).

## Output

Findings in category `engagement` or `mobile` with quoted labels, URL lists, and orientation metrics.

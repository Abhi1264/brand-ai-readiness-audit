---
name: structured-data-audit
description: Infer what a website represents, then check whether JSON-LD, schema.org, Open Graph, and meta tags describe those entities consistently with visible content. Use when auditing machine-understandable Organization, Product, Article, or LocalBusiness markup. Do not demand schema types the site does not need.
license: MIT
compatibility: Requires Python 3.11+. Operates on crawled HTML; no extra services. Skill scripts import the marketplace's brand_ai_readiness package - run `pip install -e .` from the marketplace root, or run from a checkout that contains src/.
metadata:
  author: brand-ai-readiness-audit
  version: "1.0.0"
allowed-tools: Read Bash
---

# Structured data audit

## When to use

Use this skill to answer: **Can machines understand the entities this website actually represents?**

## Inputs

- A crawl snapshot or HTML files from the target site

## Procedure

1. Infer site type from reusable signals (product/price language, docs, articles, local hours, donate, admissions). Never hardcode domains.
2. Parse JSON-LD (`scripts/jsonld.py`), Open Graph, and meta description (`scripts/metadata.py`). Record parse errors separately from missing markup.
3. Choose expected types from the inferred class (`scripts/schema_analysis.py`). Examples:
   - ecommerce → Organization, Product, Offer
   - article → Organization, Article
   - local business → LocalBusiness, PostalAddress
   - corporate/SaaS → Organization, WebSite
4. Compare structured `name` / `price` / `url` to visible text. Report mismatches only when the structured value is clearly absent from the page.
5. Phrase coverage as "0/N crawled pages contained JSON-LD", not "the website has no JSON-LD anywhere."

Do not recommend FAQ schema just because FAQ schema exists.

Details: [references/structured-data-checks.md](references/structured-data-checks.md).

## Output

Findings in category `structured_data` with observed types, page counts, and mismatch examples.

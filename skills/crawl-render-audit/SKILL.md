---
name: crawl-render-audit
description: Determine whether automated systems can reach and read a website's important content. Checks robots.txt, HTTP status, redirects, canonicals, sitemaps, raw HTML vs browser-rendered HTML, and image-only facts. Use when auditing crawlability, JS-render gaps, or machine-readability. Read-only; never bypass robots.txt.
license: MIT
compatibility: Requires Python 3.11+ and GET/HEAD network access. Playwright optional for rendering.
metadata:
  author: brand-ai-readiness-audit
  version: "1.0.0"
allowed-tools: Read Bash
---

# Crawl and render audit

## When to use

Use this skill to answer: **Can automated systems reach and read the site's important content?**

## Inputs

- Website URL, or a saved HTML pair for raw-vs-rendered comparison
- Optional crawl budget (`--max-pages`)

## Procedure

1. Normalize the start URL (strip fragment, drop tracking params, lowercase host).
2. Fetch `robots.txt`. Parse it. **Do not circumvent Disallow.** Record blocked important URLs as evidence; do not flag robots.txt merely for existing.
3. Discover sitemaps from robots.txt and common paths. Extract same-origin `<loc>` values only.
4. Crawl same-origin pages with a priority queue: homepage, sitemap, homepage links, about, product/service, pricing, contact, landings, articles. Default budget ~40 pages.
5. Record per URL: status, redirects, content-type, canonical, robots meta, internal links, `success|partial|failed`.
6. Select up to ~8 representative pages and render them (desktop + mobile) if Playwright is available. If not, set `rendering_status=unavailable` and continue.
7. Compare raw visible text to rendered text. Emit a finding only when meaningful facts (name, price, description, CTA, structured data) appear only after render.
8. Flag image/canvas-only facts when the equivalent claim is not present as HTML text. Ignore decorative images.

Scripts: `scripts/crawler.py`, `scripts/robots.py`, `scripts/renderer.py`, `scripts/render_compare.py`.

Details: [references/crawl-checks.md](references/crawl-checks.md).

## Output

Findings in category `crawlability`, `rendering`, or `machine_readability` with concrete metrics (`pages_checked`, `blocked_urls`, word counts).

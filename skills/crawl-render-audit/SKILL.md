---
name: crawl-render-audit
description: Determine whether automated systems can reach and read a website's important content. Checks robots.txt, whether the origin actually serves AI SEARCH crawlers (OAI-SearchBot, Claude-SearchBot, PerplexityBot) the same content it serves a browser, snippet-suppression directives in both markup and HTTP headers, HTTP status, redirects, canonicals, sitemaps, raw HTML vs browser-rendered HTML, and image-only facts. Use when auditing crawlability, JS-render gaps, or machine-readability. Read-only; never bypass robots.txt.
license: MIT
compatibility: Requires Python 3.11+ and GET/HEAD network access. Playwright optional for rendering. Skill scripts import the marketplace's brand_ai_readiness package - run `pip install -e .` from the marketplace root, or run from a checkout that contains src/.
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
3. **Probe actual access.** robots.txt is a request a crawler chooses to honor; the CDN/WAF decides
   what is really served. Fetch the start URL once per identity and compare status codes.

   **Probe the right class of bot.** Only search-class crawlers decide whether a brand can be
   cited: `OAI-SearchBot` (ChatGPT search), `Claude-SearchBot`, `PerplexityBot`. `GPTBot`,
   `ClaudeBot` and `CCBot` are training crawlers, and `Google-Extended` does not affect AI
   Overviews at all. Blocking training bots while allowing search bots is a deliberate,
   vendor-supported configuration -- opt out of training, stay citable -- and must **never** be
   reported as a defect. Probe the training agents for context only.

   Cross-reference the search-class results against the robots verdict for each agent:

   | robots.txt | Server | Report as |
   | --- | --- | --- |
   | allows | **blocks** | `critical` — silent invisibility the owner is unlikely to know about |
   | blocks | blocks | `medium` — consistent, deliberate exclusion; confirm it is intended |
   | blocks | allows | no finding — nothing is being denied |
   | *unreadable* | blocks | `high` — blocked, but the declared policy is unknown |
   | allows | allows | no finding |

   Trigger only on a **status** divergence. Body-length differences alone are not evidence:
   personalization, A/B tests, geo variants and cookie walls all move body size. If the browser
   identity is itself refused (paywall, geo-block, auth wall), emit nothing — that is not bot policy.
   Treat a permissive robots verdict as meaningful only when robots.txt was actually readable.
   This probe is one bounded request per agent against one URL, and is deliberately not gated on
   robots.txt, because a site that disallows the audit's own agent would otherwise yield no data at
   all. A block is recorded as a finding, never circumvented.
4. Discover sitemaps from robots.txt and common paths. Extract same-origin `<loc>` values only.
5. Crawl same-origin pages with a priority queue: homepage, sitemap, homepage links, about, product/service, pricing, contact, landings, articles. Default budget ~40 pages.
6. Record per URL: status, redirects, content-type, canonical, robots meta, internal links, `success|partial|failed`.
7. Select up to ~8 representative pages and render them (desktop + mobile) if Playwright is available. If not, set `rendering_status=unavailable` and continue.
8. Compare raw visible text to rendered text. Emit a finding only when meaningful facts (name, price, description, CTA, structured data) appear only after render.
9. Flag image/canvas-only facts when the equivalent claim is not present as HTML text. Ignore decorative images.
10. **Check snippet suppression in both places.** `nosnippet` prevents content being used as a
    direct input for AI Overviews and AI Mode, not merely from showing a search snippet, so it is
    a kill switch for citation. Read the robots meta tag **and** the `X-Robots-Tag` response
    header -- either alone suppresses the page, and a CDN or framework often adds the header with
    nothing visible in the markup. Treat `max-snippet:-1` as unlimited and never report it; only
    low positive values limit the quotable text. `data-nosnippet` on a byline or price is routine,
    so report it only when it covers most of the body. Restrict all of this to content-bearing
    pages: `nosnippet` on a terms or account page is ordinary practice.

Scripts: `scripts/crawler.py`, `scripts/robots.py`, `scripts/access_probe.py`, `scripts/renderer.py`, `scripts/render_compare.py`.

Details: [references/crawl-checks.md](references/crawl-checks.md).

## Output

Findings in category `crawlability`, `rendering`, or `machine_readability` with concrete metrics (`pages_checked`, `blocked_urls`, word counts).

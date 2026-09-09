# AI-readiness audit — 127.0.0.1

Audited 2026-09-09 09:21:16 UTC · inferred site type: **ecommerce**

| Severity | Count |
| --- | ---: |
| Critical | 0 |
| High | 2 |
| Medium | 1 |
| Low | 2 |
| **Total** | **5** |

## Scores

| AI discoverability | On-site engagement | Overall |
| ---: | ---: | ---: |
| 77 | 59 | 69 |

<details><summary>Component scores</summary>

| Component | Score |
| --- | ---: |
| crawlability | 100 |
| machine readability | 100 |
| structured data | 35 |
| entity clarity | 80 |
| freshness transparency | 40 |
| homepage orientation | 70 |
| navigation | 64 |
| cta clarity | 45 |
| internal linking | 50 |
| mobile | 60 |

</details>

## Start here

1. **No JSON-LD structured data was observed on crawled pages** (`HIGH`) — Add JSON-LD that matches this site's apparent type (ecommerce), starting with Organization, WebSite, Product.
2. **Important pages return non-2xx HTTP status** (`HIGH`) — Restore 2xx responses for public important URLs or 301 them to live replacements.
3. **Broken internal links were observed during the crawl** (`MEDIUM`) — Fix or redirect the broken internal targets and remove stale hrefs.

Findings below are ordered so the first one is the first fix.

## Findings

### 1. No JSON-LD structured data was observed on crawled pages

`HIGH` · `F-001` · structured_data · confidence 86%

**Why this happens.** Without explicit schema.org objects, machines must guess entities from prose.

**What it costs.** The site is harder to cite as a typed Organization, Product, or Article.

**Evidence.**

> No parseable JSON-LD was observed on 1 crawled HTML page(s). This is a coverage statement about the crawled set, not a claim about unfetched URLs. Metrics: pages_checked=1; jsonld_pages=0; site_type=ecommerce. Observed on: http://127.0.0.1:8877/.

**Fix (high priority).** Add JSON-LD that matches this site's apparent type (ecommerce), starting with Organization, WebSite, Product.

Infer type from the site's own content. Do not add Product schema to a campus site.

### 2. Important pages return non-2xx HTTP status

`HIGH` · `F-002` · crawlability · confidence 93%

**Why this happens.** Crawlers drop or distrust URLs that do not return a successful status.

**What it costs.** Those URLs cannot be reliably indexed or cited.

**Evidence.**

> 2 important page(s) returned non-2xx status among 3 attempts. Metrics: status_codes=(http://127.0.0.1:8877/about: 404, http://127.0.0.1:8877/products/jacket: 404). Observed on: http://127.0.0.1:8877/about, http://127.0.0.1:8877/products/jacket.

**Fix (high priority).** Restore 2xx responses for public important URLs or 301 them to live replacements.

### 3. Broken internal links were observed during the crawl

`MEDIUM` · `F-003` · crawlability · confidence 90%

**Why this happens.** Dead internal links waste crawl budget and strand visitors.

**What it costs.** Both humans and machines fail to reach the promised page.

**Evidence.**

> 2 internal URL(s) linked from crawled pages returned 404/410. Metrics: broken_urls=http://127.0.0.1:8877/products/jacket, http://127.0.0.1:8877/about; pages_checked=3; merged_EG-005=(broken_urls: http://127.0.0.1:8877/about, http://127.0.0.1:8877/products/jacket). Observed on: http://127.0.0.1:8877/products/jacket, http://127.0.0.1:8877/about. Also observed via EG-005: Visitors are sent to broken internal URLs

**Fix (medium priority).** Fix or redirect the broken internal targets and remove stale hrefs.

### 4. No Open Graph title/description metadata was observed

`LOW` · `F-004` · structured_data · confidence 72%

**Why this happens.** og:title and og:description are a widely consumed fallback when JSON-LD is absent.

**What it costs.** Link unfurls and some crawlers get a weaker title/description pair.

**Evidence.**

> 0/1 crawled page(s) exposed og:* meta tags. Metrics: pages_checked=1. Observed on: http://127.0.0.1:8877/.

**Fix (medium priority).** Add og:title, og:description, and og:url on the homepage and key templates.

### 5. Homepage never states who the offering is for

`LOW` · `F-005` · engagement · confidence 68%

**Why this happens.** Without an audience phrase, visitors cannot self-qualify and assistants omit the 'for whom' clause.

**What it costs.** Weaker engagement and weaker citations in 'best X for Y' questions.

**Evidence.**

> No 'for <audience>' / 'built for' phrasing was observed on the homepage. Metrics: site_type=ecommerce; h1=Outdoor apparel for weekend hikers. Observed on: http://127.0.0.1:8877/.

**Fix (medium priority).** Add one clause naming the intended customer or visitor on the homepage.

## Opportunities beyond the defects found

These are not problems. They are changes that would strengthen how the brand is found, read and quoted.

- **Introduce Product markup on the product template**
  - Why it matters: The crawl already found product-like URLs; typed offers would make them citable.
  - What to change: Add Product JSON-LD that repeats the visible name and price.
  - Expected benefit: Higher chance of being selected as a source for product questions.
- **Keep commercially important strings in the initial HTML even if the UI is a JS app**
  - Why it matters: This audit could not fully rely on a browser; many assistants are in the same position.
  - What to change: Prerender title, primary description, and prices, or duplicate them in JSON-LD.
  - Expected benefit: Discoverability no longer depends on a headless browser.

## What this audit checked, and what it could not

Crawled **1** of 3 discovered URLs · rendered 0 · rendering `skipped` · corroboration `unavailable` · AI-crawler probe `complete`

Limits on what can be concluded from this run:

- Browser rendering was skipped; raw-vs-rendered gaps may be under-counted.
- Independent corroboration was not run (corroboration_status=unavailable).
- Crawl budget stopped at 1 of 3 discovered URLs.

Findings describe the pages that were crawled. A signal not observed on those pages is reported as absent from them, never as absent from the whole site.

---

Generated by the `brand-ai-readiness-audit` skill marketplace. Read-only: this audit reports and recommends, and never modifies the site it audits.


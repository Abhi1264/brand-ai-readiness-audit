# Orchestration rules

## Composition

The crawler runs once. Every other skill reads the same `CrawlSnapshot`.

| Skill | Writes into the snapshot / findings |
| --- | --- |
| crawl-render-audit | pages, robots, access probes, sitemap, renders, CR-* findings |
| structured-data-audit | `structured`, site_type, SD-* findings |
| freshness-entity-audit | entities, claims, FE-* findings |
| engagement-audit | EG-* findings |
| audit-orchestrator | dedupe, severity, order, proactive recs, validation |

## Dedup

Treat these as one finding when URLs overlap:

- `broken_internal_links` from crawl and engagement
- `js_content_gap` plus a generic "content hard to access" note — keep the render-gap finding; fold extra evidence into it
- `robots_blocks_important` plus `ai_crawler_excluded_by_policy` — one root cause. The probe finding
  is suppressed when the robots finding already fired, so they never both appear.
- `ai_crawler_edge_blocked`, `ai_crawler_excluded_by_policy` and
  `ai_crawler_blocked_robots_unknown` are mutually exclusive by construction: robots
  allows/blocks/was-unreadable respectively, against a server block.

## Severity

Implemented in `brand_ai_readiness.scoring.severity`:

- CRITICAL: fundamental barrier (homepage down, important URLs all robots-blocked, or the origin
  refuses AI crawlers that robots.txt explicitly permits)
- HIGH: important pages or important facts affected with high confidence
- MEDIUM: real weakness, limited scope
- LOW: optimization

Never let an LLM assign severity.

## Language

- "not observed on N crawled pages" ≠ "does not exist"
- "corroboration_status=unavailable" ≠ "claim is false"
- "robots.txt exists" is not a finding
- "JavaScript exists" is not a finding
- a deliberate, consistent AI-crawler exclusion is a policy observation, not a defect — report it
  as something to confirm, never as a mistake

## Safety

GET and HEAD only. Same-origin unless configured. Honor robots.txt. Bound pages, bytes, time, and concurrency.

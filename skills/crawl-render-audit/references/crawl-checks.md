# Crawl and render checks

## Always collect

- robots.txt availability and the Disallow patterns that actually matched audited URLs
- what the origin serves a browser vs GPTBot / ClaudeBot / PerplexityBot (status per identity)
- HTTP status and redirect chain
- content-type
- canonical href vs fetched URL
- robots meta / noindex
- sitemap loc entries
- internal links
- raw visible-text word count
- rendered word count when a browser is available

## Emit a finding only if

| Signal | Finding |
| --- | --- |
| Important URL disallowed | robots blocks important pages |
| robots allows an AI agent but the origin 4xx/5xx it | AI crawler blocked at the edge (`critical`) |
| robots disallows an AI agent and the origin also refuses it | deliberate exclusion (`medium`) |
| an AI agent is refused and robots.txt was unreadable | blocked, policy unknown (`high`) |
| Important URL 4xx/5xx | HTTP failure |
| redirect_loop / excessive_redirects | redirect failure |
| noindex on homepage/product/about | noindex important |
| sitemap listed but unusable | sitemap inaccessible |
| meaningful render gap | JS content gap |
| fact-like alt/canvas without text | image-only facts |
| linked 404/410 | broken internal links |

## Do not emit

- "robots.txt exists"
- "the site uses JavaScript"
- "images exist"
- an AI-crawler block inferred from body-length differences alone (status divergence is required)
- an AI-crawler block when the browser identity was refused too — that is a paywall or geo-block,
  not bot policy
- "we only crawled N pages, therefore the whole site lacks X" without stating N

## AI-crawler access probe

Identities used, and why each is worth probing separately:

| Agent | Used by |
| --- | --- |
| `GPTBot` | OpenAI crawling for retrieval/training |
| `ClaudeBot` | Anthropic crawling |
| `PerplexityBot` | Perplexity's index |
| browser UA | control — establishes that the origin serves anyone at all |

The probe answers a question robots.txt cannot: **do the declared policy and the enforced policy
agree?** A site can publish a permissive robots.txt and still return 403 from a bot-management rule
(Cloudflare "Block AI Bots", Akamai Bot Manager, or a server-level user-agent deny). Nothing in the
robots file reveals that, and the site owner usually does not know.

A permissive robots verdict only counts when robots.txt was actually readable. When it was not,
the parser defaults to allow for crawling purposes, but "we could not read robots.txt" is not the
claim "robots.txt permits this agent" — reporting it as the latter invents a contradiction that
was never observed. That case is reported separately, below critical.

Constraints: HEAD first and GET only if the origin does not implement HEAD (400/405/501); one URL;
one request per identity; no retries and an 8s deadline, so an origin that tarpits unfamiliar
agents cannot consume the audit's time budget; never used to retrieve content the audit's own
user-agent was denied.

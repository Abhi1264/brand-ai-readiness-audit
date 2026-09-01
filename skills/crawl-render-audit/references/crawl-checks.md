# Crawl and render checks

## Always collect

- robots.txt availability and the Disallow patterns that actually matched audited URLs
- what the origin serves a browser vs each AI crawler, recorded per identity and per class
- robots meta AND X-Robots-Tag header directives (nosnippet, max-snippet, noindex)
- data-nosnippet coverage as a share of the page's visible text
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
| robots allows a SEARCH agent but the origin 4xx/5xx it | AI crawler blocked at the edge (`critical`) |
| robots disallows an AI agent and the origin also refuses it | deliberate exclusion (`medium`) |
| a SEARCH agent is refused and robots.txt was unreadable | blocked, policy unknown (`high`) |
| nosnippet on content pages (meta or header) | content withheld from AI surfaces (`high`) |
| max-snippet set to a low positive value | quotable text truncated (`medium`) |
| data-nosnippet over most of the body | body not quotable (`medium`) |
| noindex in X-Robots-Tag but not in the markup | hidden exclusion (`high`) |
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

| Agent | Class | Decides citation? |
| --- | --- | --- |
| `OAI-SearchBot` | search | **yes** — opting out removes the site from ChatGPT search answers |
| `Claude-SearchBot` | search | **yes** |
| `PerplexityBot` | search | **yes** — not used for foundation-model training |
| `GPTBot` | training | no |
| `ClaudeBot` | training | no |
| `CCBot` | training | no |
| `Google-Extended` | training | no — does not affect Google Search or AI Overviews |
| browser UA | control | establishes that the origin serves anyone at all |

**Only search-class blocks are findings.** Blocking training crawlers while allowing search
crawlers is a deliberate, vendor-supported configuration, and reporting it as a defect would flag
the most common intentional setup as broken. Training results are recorded as context.

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

## Snippet suppression

`nosnippet` is documented by Google as preventing content "from being used as a direct input for
AI Overviews and AI Mode" -- it is stronger than a search-snippet setting and is the most direct
on-page opt-out from AI citation that exists. `max-snippet` limits how much may be used.

Both arrive from two independent places, and either alone is sufficient:

- the robots `<meta>` tag, visible in the markup
- the `X-Robots-Tag` response header, invisible to anything that only parses HTML

A checker that reads only the markup cannot see the second, and the two can disagree. The same
applies to `rel=canonical`, which may also be set via a `Link:` header.

False-positive guards: `max-snippet:-1` means unlimited and is never reported; `data-nosnippet`
is expected on small elements and is reported only when it covers most of the body; and all of
these are restricted to content-bearing roles, since suppressing a terms or account page is
ordinary practice.

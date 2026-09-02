from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_USER_AGENT = (
    "BrandAIReadinessAudit/1.0 (+https://github.com/adobe-university-hackathon/"
    "brand-ai-readiness-audit; recommend-only; read-only)"
)

# Diagnostic identities used only by the access probe (crawler/access_probe.py).
# The probe measures who the origin lets in; it never uses these to retrieve
# content that the honest audit user-agent was denied.
BROWSER_PROBE_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Crawlers split into two classes, and conflating them produces a false
# positive. Only SEARCH-class bots decide whether a brand can be cited:
#   OpenAI  - "Sites that are opted out of OAI-SearchBot will not be shown in
#             ChatGPT search answers." GPTBot is training only.
#   Anthropic - Claude-SearchBot serves search quality; ClaudeBot is training.
#   Perplexity - PerplexityBot surfaces search; "not used to crawl content for
#             AI foundation models".
# Blocking training-class bots while allowing search-class ones is a deliberate,
# vendor-supported configuration -- opt out of training, stay citable. It must
# never be reported as a discoverability defect.
AI_SEARCH_PROBE_AGENTS: dict[str, str] = {
    "OAI-SearchBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
        "OAI-SearchBot/1.0; +https://openai.com/searchbot"
    ),
    "Claude-SearchBot": (
        "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +claudebot@anthropic.com)"
    ),
    "PerplexityBot": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko); compatible; PerplexityBot/1.0; "
        "+https://perplexity.ai/perplexitybot"
    ),
}

# Probed for context only. A block here is a licensing/policy choice, not a
# citation problem, and never raises a finding on its own.
AI_TRAINING_PROBE_AGENTS: dict[str, str] = {
    "GPTBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
        "GPTBot/1.1; +https://openai.com/gptbot"
    ),
    "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "CCBot": "CCBot/2.0 (https://commoncrawl.org/faq/)",
}

SAFE_METHODS = frozenset({"GET", "HEAD"})

TRACKING_QUERY_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "_ga",
        "ref",
        "ref_src",
    }
)


@dataclass(frozen=True)
class AuditBudget:
    max_pages: int = 40
    max_renders: int = 8
    request_timeout_s: float = 15.0
    max_concurrency: int = 4
    max_response_bytes: int = 2_000_000
    max_retries: int = 2
    same_origin_only: bool = True
    respect_robots: bool = True
    max_redirects: int = 8
    render_timeout_s: float = 20.0
    desktop_viewport: tuple[int, int] = (1280, 800)
    mobile_viewport: tuple[int, int] = (390, 844)
    enable_render: bool = True
    enable_llm_polish: bool = False
    enable_access_probe: bool = True
    # Max pages crawled from one deep URL family (e.g. /jobs/location/*), so a
    # single facet family cannot consume the whole page budget.
    max_pages_per_url_family: int = 8
    user_agent: str = DEFAULT_USER_AGENT
    extra_allowed_hosts: tuple[str, ...] = field(default_factory=tuple)

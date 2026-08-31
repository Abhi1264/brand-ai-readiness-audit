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

AI_CRAWLER_PROBE_AGENTS: dict[str, str] = {
    "GPTBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
        "GPTBot/1.1; +https://openai.com/gptbot"
    ),
    "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko); compatible; PerplexityBot/1.0; "
        "+https://perplexity.ai/perplexitybot"
    ),
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
    user_agent: str = DEFAULT_USER_AGENT
    extra_allowed_hosts: tuple[str, ...] = field(default_factory=tuple)


DEFAULT_BUDGET = AuditBudget()

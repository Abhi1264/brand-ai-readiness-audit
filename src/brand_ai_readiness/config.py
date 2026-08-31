"""Runtime budgets and safety defaults.

All values are conservative so a typical audit finishes in well under 5 minutes
and never mutates a target site.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_USER_AGENT = (
    "BrandAIReadinessAudit/1.0 (+https://github.com/adobe-university-hackathon/"
    "brand-ai-readiness-audit; recommend-only; read-only)"
)

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
    """Configurable crawl / render / analysis limits."""

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
    user_agent: str = DEFAULT_USER_AGENT
    extra_allowed_hosts: tuple[str, ...] = field(default_factory=tuple)


DEFAULT_BUDGET = AuditBudget()

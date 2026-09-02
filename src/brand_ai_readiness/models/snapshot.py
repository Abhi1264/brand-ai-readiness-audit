from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PageFetchStatus = Literal["success", "partial", "failed"]
BotClass = Literal["browser", "search", "training"]
AccessProbeStatus = Literal["complete", "partial", "unavailable", "skipped"]
SiteType = Literal[
    "ecommerce",
    "article",
    "corporate",
    "local_business",
    "saas",
    "docs",
    "nonprofit",
    "university",
    "mixed",
    "unknown",
]
PageRole = Literal[
    "homepage",
    "about",
    "product",
    "service",
    "pricing",
    "contact",
    "article",
    "docs",
    "landing",
    "legal",
    "other",
]


class FetchedPage(BaseModel):
    url: str
    final_url: str
    status_code: int = 0
    content_type: str = ""
    html: str = ""
    text: str = ""
    title: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    redirect_chain: list[str] = Field(default_factory=list)
    fetch_status: PageFetchStatus = "success"
    error: str | None = None
    retry_count: int = 0
    robots_blocked: bool = False
    canonical: str | None = None
    robots_meta: str | None = None
    noindex: bool = False
    internal_links: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    role: PageRole = "other"
    word_count: int = 0
    heading_count: int = 0


class RenderedPage(BaseModel):
    url: str
    html: str = ""
    visible_text: str = ""
    viewport: str = "desktop"
    word_count: int = 0
    heading_count: int = 0
    link_count: int = 0
    jsonld_count: int = 0
    overflow_x: bool = False
    nav_visible: bool = True
    cta_visible: bool = True
    min_font_px: float | None = None
    error: str | None = None


class RobotsInfo(BaseModel):
    url: str
    available: bool = False
    raw: str | None = None
    sitemaps: list[str] = Field(default_factory=list)
    disallow_patterns: list[str] = Field(default_factory=list)
    blocked_urls: list[str] = Field(default_factory=list)
    parse_error: str | None = None


class AccessProbeResult(BaseModel):
    """One diagnostic request to the same URL under a named identity.

    Used to compare what a browser is served against what a named AI crawler is
    served. Read-only, one URL, one request per agent.
    """

    agent: str
    user_agent: str
    is_ai_crawler: bool = False
    # "search" bots decide citation; "training" bots do not. Only the former
    # can raise a discoverability finding.
    bot_class: BotClass = "browser"
    status_code: int = 0
    method: str = "HEAD"
    body_bytes: int = 0
    error: str | None = None
    robots_allows: bool = True

    def reachable(self) -> bool:
        return 200 <= self.status_code < 400


class SitemapInfo(BaseModel):
    discovered: list[str] = Field(default_factory=list)
    accessible: bool = False
    urls: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CrawlStats(BaseModel):
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_rendered: int = 0
    pages_failed: int = 0
    pages_blocked: int = 0
    pages_partial: int = 0
    rendering_status: Literal["complete", "partial", "unavailable", "skipped"] = "skipped"


class ExtractedClaim(BaseModel):
    claim: str
    source_url: str
    source_page: str
    evidence_text: str
    importance: Literal["high", "medium", "low"] = "medium"
    freshness_signal: str = "none"
    entity: str = ""


class EntityRecord(BaseModel):
    name: str
    kind: Literal["organization", "brand", "product", "service", "person", "location"]
    sources: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)


class StructuredBlock(BaseModel):
    url: str
    kind: Literal["jsonld", "opengraph", "meta", "microdata"]
    types: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    parse_error: str | None = None


class CrawlSnapshot(BaseModel):
    start_url: str
    site: str
    pages: list[FetchedPage] = Field(default_factory=list)
    rendered: list[RenderedPage] = Field(default_factory=list)
    robots: RobotsInfo
    sitemap: SitemapInfo = Field(default_factory=SitemapInfo)
    stats: CrawlStats = Field(default_factory=CrawlStats)
    site_type: SiteType = "unknown"
    site_type_signals: list[str] = Field(default_factory=list)
    claims: list[ExtractedClaim] = Field(default_factory=list)
    entities: list[EntityRecord] = Field(default_factory=list)
    structured: list[StructuredBlock] = Field(default_factory=list)
    corroboration_status: Literal["unavailable", "partial", "complete"] = "unavailable"
    access_probes: list[AccessProbeResult] = Field(default_factory=list)
    access_probe_status: AccessProbeStatus = "skipped"

    def browser_probe(self) -> AccessProbeResult | None:
        for probe in self.access_probes:
            if not probe.is_ai_crawler:
                return probe
        return None

    def search_probes(self) -> list[AccessProbeResult]:
        return [probe for probe in self.access_probes if probe.bot_class == "search"]

    def training_probes(self) -> list[AccessProbeResult]:
        return [probe for probe in self.access_probes if probe.bot_class == "training"]

    def successful_pages(self) -> list[FetchedPage]:
        return [page for page in self.pages if page.fetch_status == "success" and page.html]

    def homepage(self) -> FetchedPage | None:
        for page in self.pages:
            if page.role == "homepage":
                return page
        return self.pages[0] if self.pages else None

    def pages_by_role(self, role: PageRole) -> list[FetchedPage]:
        return [page for page in self.successful_pages() if page.role == role]

    def rendered_for(self, url: str, viewport: str = "desktop") -> RenderedPage | None:
        for item in self.rendered:
            if item.url == url and item.viewport == viewport and item.error is None:
                return item
        return None

    def desktop_rendered(self, page: FetchedPage) -> RenderedPage | None:
        return self.rendered_for(page.url, "desktop") or self.rendered_for(page.final_url, "desktop")

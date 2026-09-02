from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import replace
from urllib.parse import urljoin, urlparse

import httpx

from brand_ai_readiness.analysis.html import (
    canonical_href,
    extract_links,
    has_noindex,
    headings,
    parse_html,
    robots_meta,
    title_text,
    visible_text,
    word_count,
)
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.crawler.access_probe import probe_access
from brand_ai_readiness.crawler.fetcher import decode_body, fetch_bytes
from brand_ai_readiness.crawler.priority import classify_role, url_priority
from brand_ai_readiness.crawler.robots import RobotsPolicy, empty_robots, parse_robots
from brand_ai_readiness.crawler.sitemap import (
    decode_sitemap_bytes,
    default_sitemap_guesses,
    merge_sitemap_info,
    parse_sitemap_document,
)
from brand_ai_readiness.crawler.urls import (
    is_probably_asset,
    normalize_url,
    origin_of,
    same_origin,
    site_label,
)
from brand_ai_readiness.models.snapshot import (
    AccessProbeResult,
    AccessProbeStatus,
    CrawlSnapshot,
    CrawlStats,
    FetchedPage,
    PageFetchStatus,
    RobotsInfo,
    SitemapInfo,
)

logger = logging.getLogger(__name__)


def _is_html(content_type: str, body: bytes) -> bool:
    lowered = content_type.lower()
    if "html" in lowered or "xml" in lowered or lowered in {"", "text/plain"}:
        return True
    prefix = body[:200].lstrip().lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html")


class BoundedCrawler:
    def __init__(self, start_url: str, budget: AuditBudget | None = None) -> None:
        self.start_url = normalize_url(start_url) or start_url
        self.budget = budget or AuditBudget()
        self.origin = origin_of(self.start_url)
        self._queue: list[tuple[int, int, str, dict[str, bool]]] = []
        self._seq = 0
        self._seen: set[str] = set()
        self._enqueued: set[str] = set()
        self._family_counts: dict[str, int] = {}
        self.pages: list[FetchedPage] = []
        self.blocked: list[str] = []
        self.robots_policy: RobotsPolicy = empty_robots(self.start_url)
        self.sitemap = SitemapInfo()
        self.access_probes: list[AccessProbeResult] = []
        self.access_probe_status: AccessProbeStatus = "skipped"

    def _allowed_host(self, url: str) -> bool:
        if same_origin(url, self.start_url):
            return True
        if not self.budget.same_origin_only:
            return True
        extras = {host.lower() for host in self.budget.extra_allowed_hosts}
        return (urlparse(url).hostname or "").lower() in extras

    def _url_family(self, url: str) -> str | None:
        """Group key for sibling URLs under a deep shared prefix.

        Only paths at least three segments deep have a family: those are facet
        or filter families ("/jobs/location/warsaw-poland"). Top-level sections
        like "/products/widget" or a locale prefix like "/en/about" are left
        uncapped, because those are the pages an audit actually wants.
        """
        segments = [segment for segment in (urlparse(url).path or "/").split("/") if segment]
        if len(segments) < 3:
            return None
        return "/".join(segments[:-1])

    def enqueue(self, url: str, *, from_sitemap: bool = False, from_homepage: bool = False) -> None:
        normalized = normalize_url(url, self.start_url)
        if not normalized or normalized in self._seen or normalized in self._enqueued:
            return
        if is_probably_asset(normalized):
            return
        if not self._allowed_host(normalized):
            return
        family = self._url_family(normalized)
        if family is not None:
            seen_in_family = self._family_counts.get(family, 0)
            if seen_in_family >= self.budget.max_pages_per_url_family:
                return
            self._family_counts[family] = seen_in_family + 1
        self._seq += 1
        priority = -url_priority(normalized, from_sitemap=from_sitemap, from_homepage=from_homepage)
        heapq.heappush(
            self._queue,
            (priority, self._seq, normalized, {"from_sitemap": from_sitemap, "from_homepage": from_homepage}),
        )
        self._enqueued.add(normalized)

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        robots_url = urljoin(self.origin + "/", "robots.txt")
        result = await fetch_bytes(client, robots_url, self.budget)
        if result.status_code == 200 and result.body:
            text = decode_body(result.body, result.content_type)
            self.robots_policy = parse_robots(text, robots_url, self.budget.user_agent)
        else:
            info = RobotsInfo(url=robots_url, available=False)
            self.robots_policy.info = info

    async def _load_sitemaps(self, client: httpx.AsyncClient) -> None:
        candidates = list(self.robots_policy.info.sitemaps) + default_sitemap_guesses(self.origin)
        discovered: list[str] = []
        urls: list[str] = []
        errors: list[str] = []
        seen_maps: set[str] = set()
        while candidates and len(seen_maps) < 12:
            raw = candidates.pop(0)
            sitemap_url = normalize_url(raw, self.origin) or raw
            if sitemap_url in seen_maps:
                continue
            seen_maps.add(sitemap_url)
            result = await fetch_bytes(client, sitemap_url, self.budget)
            if result.status_code != 200 or not result.body:
                errors.append(f"{sitemap_url} status={result.status_code or result.error}")
                continue
            text, skip = decode_sitemap_bytes(result.body, result.content_type)
            if skip or not text:
                errors.append(f"{sitemap_url} skipped ({skip or 'empty'})")
                continue
            pages, children = parse_sitemap_document(text, sitemap_url, self.start_url)
            discovered.append(sitemap_url)
            if not pages and not children:
                errors.append(f"{sitemap_url} contained no same-origin loc entries")
            urls.extend(pages)
            for child in children:
                if child not in seen_maps:
                    candidates.append(child)
        self.sitemap = merge_sitemap_info(discovered, urls, errors)
        for item in self.sitemap.urls:
            self.enqueue(item, from_sitemap=True)

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> FetchedPage:
        if self.budget.respect_robots and not self.robots_policy.allows(url):
            self.blocked.append(url)
            self.robots_policy.info.blocked_urls.append(url)
            return FetchedPage(
                url=url,
                final_url=url,
                fetch_status="failed",
                error="robots_disallow",
                robots_blocked=True,
                role=classify_role(url),
            )
        result = await fetch_bytes(client, url, self.budget)
        role = classify_role(result.final_url or url)
        if result.error and result.status_code == 0:
            return FetchedPage(
                url=url,
                final_url=result.final_url,
                status_code=result.status_code,
                content_type=result.content_type,
                fetch_status="failed",
                error=result.error,
                retry_count=result.retry_count,
                redirect_chain=result.redirect_chain,
                role=role,
            )
        html = ""
        text = ""
        title = None
        canonical = None
        robots = None
        noindex = False
        internal: list[str] = []
        external: list[str] = []
        heading_count = 0
        status: PageFetchStatus = "success"
        error = result.error
        if 200 <= result.status_code < 300 and _is_html(result.content_type, result.body):
            html = decode_body(result.body, result.content_type)
            soup = parse_html(html)
            text = visible_text(soup)
            title = title_text(soup)
            canonical = canonical_href(soup, result.final_url)
            robots = robots_meta(soup)
            noindex = has_noindex(robots)
            internal, external = extract_links(soup, result.final_url)
            heading_count = len(headings(soup))
        elif 200 <= result.status_code < 300:
            status = "partial"
            error = error or "non_html"
        else:
            status = "failed"
            error = error or f"http_{result.status_code}"
            if result.body and _is_html(result.content_type, result.body):
                html = decode_body(result.body, result.content_type)
                soup = parse_html(html)
                text = visible_text(soup)
                title = title_text(soup)
                status = "partial"
        return FetchedPage(
            url=url,
            final_url=result.final_url,
            status_code=result.status_code,
            content_type=result.content_type,
            html=html,
            text=text,
            title=title,
            headers=result.headers,
            redirect_chain=result.redirect_chain,
            fetch_status=status,
            error=error,
            retry_count=result.retry_count,
            canonical=canonical,
            robots_meta=robots,
            noindex=noindex,
            internal_links=internal,
            external_links=external,
            role=role,
            word_count=word_count(text),
            heading_count=heading_count,
        )

    async def _run_access_probe(self, client: httpx.AsyncClient) -> None:
        """Measure who the origin actually serves. Never blocks the audit."""
        try:
            self.access_probes = await probe_access(
                client, self.start_url, self.budget, self.robots_policy
            )
        except Exception as exc:
            logger.info("access probe unavailable: %s", exc)
            self.access_probes = []
        if not self.access_probes:
            self.access_probe_status = "unavailable"
            return
        browser = next((p for p in self.access_probes if not p.is_ai_crawler), None)
        ai = [p for p in self.access_probes if p.is_ai_crawler]
        if browser is None or browser.status_code == 0 or not ai:
            self.access_probe_status = "partial"
        else:
            self.access_probe_status = "complete"

    async def crawl(self, *, seed: bool = True, discover_sitemaps: bool = True) -> CrawlSnapshot:
        if seed:
            self.enqueue(self.start_url)
        limits = httpx.Limits(
            max_connections=self.budget.max_concurrency,
            max_keepalive_connections=self.budget.max_concurrency,
        )
        headers = {
            "User-Agent": self.budget.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,*/*;q=0.8",
        }
        async with httpx.AsyncClient(
            headers=headers,
            limits=limits,
            http2=False,
            follow_redirects=True,
            max_redirects=self.budget.max_redirects,
        ) as client:
            await self._load_robots(client)
            if self.budget.enable_access_probe and seed:
                await self._run_access_probe(client)
            if discover_sitemaps:
                await self._load_sitemaps(client)
            sem = asyncio.Semaphore(self.budget.max_concurrency)

            async def worker(url: str) -> FetchedPage:
                async with sem:
                    return await self._fetch_page(client, url)

            homepage_links: set[str] = set()
            while self._queue and len(self.pages) < self.budget.max_pages:
                batch: list[str] = []
                while self._queue and len(batch) < self.budget.max_concurrency:
                    if len(self.pages) + len(batch) >= self.budget.max_pages:
                        break
                    _prio, _seq, url, _meta = heapq.heappop(self._queue)
                    if url in self._seen:
                        continue
                    self._seen.add(url)
                    batch.append(url)
                if not batch:
                    break
                results = await asyncio.gather(*(worker(url) for url in batch), return_exceptions=True)
                for result in results:
                    if isinstance(result, BaseException):
                        logger.warning("page worker crashed: %s", result)
                        continue
                    self.pages.append(result)
                    if result.fetch_status == "success":
                        is_home = result.role == "homepage" or result.url == self.start_url
                        if is_home:
                            homepage_links.update(result.internal_links)
                        for link in result.internal_links:
                            self.enqueue(
                                link,
                                from_homepage=link in homepage_links or is_home,
                            )

        crawled_ok = [page for page in self.pages if page.fetch_status == "success"]
        failed = [page for page in self.pages if page.fetch_status == "failed"]
        partial = [page for page in self.pages if page.fetch_status == "partial"]
        stats = CrawlStats(
            pages_discovered=len(self._enqueued | self._seen),
            pages_crawled=len(crawled_ok),
            pages_failed=len(failed),
            pages_blocked=len(self.blocked),
            pages_partial=len(partial),
        )
        return CrawlSnapshot(
            start_url=self.start_url,
            site=site_label(self.start_url),
            pages=self.pages,
            robots=self.robots_policy.info,
            sitemap=self.sitemap,
            stats=stats,
            access_probes=self.access_probes,
            access_probe_status=self.access_probe_status,
        )


async def crawl_site(start_url: str, budget: AuditBudget | None = None) -> CrawlSnapshot:
    return await BoundedCrawler(start_url, budget).crawl()


async def crawl_additional(
    start_url: str,
    seeds: list[str],
    budget: AuditBudget,
    already_seen: set[str],
) -> list[FetchedPage]:
    remaining = budget.max_pages - len(already_seen)
    if remaining <= 0 or not seeds:
        return []
    extra_budget = replace(budget, max_pages=remaining, max_renders=0, enable_render=False)
    crawler = BoundedCrawler(start_url, extra_budget)
    crawler._seen.update(already_seen)
    crawler._enqueued.update(already_seen)
    for url in seeds:
        crawler.enqueue(url, from_homepage=True)
    extra = await crawler.crawl(seed=False, discover_sitemaps=False)
    return extra.pages


def crawl_site_sync(start_url: str, budget: AuditBudget | None = None) -> CrawlSnapshot:
    return asyncio.run(crawl_site(start_url, budget))

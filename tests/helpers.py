from __future__ import annotations

from pathlib import Path

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
from urllib.parse import urlparse

from brand_ai_readiness.crawler.priority import classify_role
from brand_ai_readiness.crawler.robots import parse_robots
from brand_ai_readiness.crawler.urls import site_label
from brand_ai_readiness.models.snapshot import (
    CrawlSnapshot,
    CrawlStats,
    FetchedPage,
    PageRole,
    RenderedPage,
    RobotsInfo,
    SitemapInfo,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sites"


def page_from_html(
    url: str,
    html: str,
    *,
    status_code: int = 200,
    role: PageRole | None = None,
    robots_blocked: bool = False,
    content_type: str = "text/html",
) -> FetchedPage:
    soup = parse_html(html)
    text = visible_text(soup)
    internal, external = extract_links(soup, url)
    robots = robots_meta(soup)
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=status_code,
        content_type=content_type,
        html=html,
        text=text,
        title=title_text(soup),
        fetch_status="failed" if robots_blocked or status_code >= 400 else "success",
        error="robots_disallow" if robots_blocked else (f"http_{status_code}" if status_code >= 400 else None),
        robots_blocked=robots_blocked,
        canonical=canonical_href(soup, url),
        robots_meta=robots,
        noindex=has_noindex(robots),
        internal_links=internal,
        external_links=external,
        role=role or classify_role(url, is_start=urlparse(url).path in {"", "/"}),
        word_count=word_count(text),
        heading_count=len(headings(soup)),
    )


def snapshot_from_pages(
    pages: list[FetchedPage],
    *,
    start_url: str,
    robots_raw: str | None = None,
    rendered: list[RenderedPage] | None = None,
    sitemap_urls: list[str] | None = None,
) -> CrawlSnapshot:
    if robots_raw:
        policy = parse_robots(robots_raw, start_url.rstrip("/") + "/robots.txt")
        robots = policy.info
    else:
        robots = RobotsInfo(url=start_url.rstrip("/") + "/robots.txt", available=False)
    blocked = sum(1 for page in pages if page.robots_blocked)
    failed = sum(1 for page in pages if page.fetch_status == "failed")
    ok = sum(1 for page in pages if page.fetch_status == "success")
    return CrawlSnapshot(
        start_url=start_url,
        site=site_label(start_url),
        pages=pages,
        rendered=rendered or [],
        robots=robots,
        sitemap=SitemapInfo(urls=sitemap_urls or [], accessible=bool(sitemap_urls), discovered=[]),
        stats=CrawlStats(
            pages_discovered=len(pages),
            pages_crawled=ok,
            pages_rendered=len({item.url for item in (rendered or []) if not item.error}),
            pages_failed=failed,
            pages_blocked=blocked,
            rendering_status="complete" if rendered else "skipped",
        ),
    )


def load_site_html(site_dir: str, filename: str) -> str:
    return (FIXTURES / site_dir / filename).read_text(encoding="utf-8")


def snapshot_from_site_dir(site_dir: str, host: str = "https://fixture.test") -> CrawlSnapshot:
    root = FIXTURES / site_dir
    pages: list[FetchedPage] = []
    robots_raw = None
    sitemap_urls: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "robots.txt":
            robots_raw = path.read_text(encoding="utf-8")
            continue
        if rel.endswith(".xml"):
            from brand_ai_readiness.crawler.sitemap import parse_sitemap_xml

            sitemap_urls.extend(parse_sitemap_xml(path.read_text(encoding="utf-8"), host, host))
            continue
        if not rel.endswith(".html"):
            continue
        url_path = "/" if rel in {"index.html"} else "/" + rel.replace(".html", "")
        if rel.endswith("/index.html") and rel != "index.html":
            url_path = "/" + rel[: -len("/index.html")]
        url = host.rstrip("/") + url_path
        html = path.read_text(encoding="utf-8")
        role = "homepage" if url_path == "/" else None
        pages.append(page_from_html(url, html, role=role))
    start = host.rstrip("/") + "/"
    return snapshot_from_pages(pages, start_url=start, robots_raw=robots_raw, sitemap_urls=sitemap_urls)

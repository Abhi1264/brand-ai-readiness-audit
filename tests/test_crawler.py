from __future__ import annotations

from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.crawler.crawler import BoundedCrawler, crawl_site_sync
from brand_ai_readiness.crawler.priority import classify_role, url_priority
import gzip

from brand_ai_readiness.crawler.sitemap import (
    decode_sitemap_bytes,
    parse_sitemap_document,
    parse_sitemap_xml,
)
from brand_ai_readiness.crawler.urls import normalize_url, same_origin, site_label


def test_normalize_strips_fragment_and_tracking():
    assert (
        normalize_url("HTTPS://Example.COM/About/?utm_source=x&id=1#team")
        == "https://example.com/About?id=1"
    )


def test_normalize_trailing_slash_dedupes():
    assert normalize_url("https://example.com/about/") == normalize_url("https://example.com/about")


def test_same_origin_and_site_label():
    assert same_origin("https://a.example/x", "https://a.example/y")
    assert not same_origin("https://a.example/", "https://b.example/")
    assert site_label("https://www.Example.com/path") == "example.com"


def test_duplicate_enqueue():
    crawler = BoundedCrawler("https://example.com/")
    crawler.enqueue("https://example.com/about")
    crawler.enqueue("https://example.com/about#x")
    crawler.enqueue("https://example.com/about?utm_source=ad")
    urls = [item[2] for item in crawler._queue]
    assert urls.count("https://example.com/about") == 1


def test_internal_vs_external_priority_roles():
    assert classify_role("https://example.com/pricing") == "pricing"
    assert classify_role("https://example.com/products/a") == "product"
    assert url_priority("https://example.com/") > url_priority("https://example.com/blog/post")


def test_sitemap_skips_html_shell():
    html = "<!doctype html><html><body>SPA</body></html>"
    text, skip = decode_sitemap_bytes(html.encode(), "text/html")
    assert text is None
    assert skip == "html_not_xml"
    assert parse_sitemap_xml(html, "https://example.com/sitemap.xml", "https://example.com/") == []


def test_sitemap_gzip_roundtrip():
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
    </urlset>"""
    compressed = gzip.compress(xml.encode())
    text, skip = decode_sitemap_bytes(compressed, "application/gzip")
    assert skip is None
    assert parse_sitemap_xml(text or "", "https://example.com/sitemap.xml", "https://example.com/") == [
        "https://example.com/a"
    ]


def test_sitemap_index_returns_child_maps():
    xml = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
    </sitemapindex>"""
    pages, children = parse_sitemap_document(xml, "https://example.com/sitemap.xml", "https://example.com/")
    assert pages == []
    assert children == ["https://example.com/sitemap-pages.xml"]


def test_sitemap_extracts_same_origin_only():
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://other.com/b</loc></url>
    </urlset>"""
    urls = parse_sitemap_xml(xml, "https://example.com/sitemap.xml", "https://example.com/")
    assert urls == ["https://example.com/a"]


def test_crawl_budget(serve_site):
    url = serve_site("01_excellent")
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=2, enable_render=False, max_concurrency=2))
    assert snapshot.stats.pages_crawled <= 2
    assert len(snapshot.successful_pages()) <= 2


def test_crawl_follows_internal_links(serve_site):
    url = serve_site("01_excellent")
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=10, enable_render=False))
    paths = {page.role for page in snapshot.successful_pages()}
    assert "homepage" in paths
    assert snapshot.stats.pages_crawled >= 3


def test_redirect_recorded(serve_site, tmp_path):
    # Excellent site has no redirects; still records a single-hop chain for the start URL.
    url = serve_site("01_excellent")
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=1, enable_render=False))
    page = snapshot.pages[0]
    assert page.redirect_chain
    assert page.status_code == 200

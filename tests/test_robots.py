from __future__ import annotations

from brand_ai_readiness.config import AuditBudget, DEFAULT_USER_AGENT
from brand_ai_readiness.crawler.crawler import crawl_site_sync
from brand_ai_readiness.crawler.robots import allows_url, parse_robots


def test_allows_unblocked_url():
    raw = "User-agent: *\nDisallow: /admin\n"
    assert allows_url(raw, "https://example.com/about")


def test_blocks_disallowed_url():
    raw = "User-agent: *\nDisallow: /private\n"
    assert not allows_url(raw, "https://example.com/private/page")


def test_robots_strips_trailing_html():
    raw = "User-agent: *\nAllow: /\n\n<!doctype html><html><body>nope</body></html>\n"
    assert allows_url(raw, "https://example.com/about")


def test_malformed_robots_does_not_raise():
    policy = parse_robots("::::\nUser-agent\nDisallow", "https://example.com/robots.txt")
    assert policy.allows("https://example.com/")


def test_robots_txt_existence_is_not_a_block():
    raw = "User-agent: *\nAllow: /\n"
    assert allows_url(raw, "https://example.com/")


def test_crawler_respects_disallow_all(serve_site):
    url = serve_site("02_robots_blocked")
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=5, enable_render=False, user_agent=DEFAULT_USER_AGENT))
    assert snapshot.stats.pages_blocked >= 1
    assert all(page.robots_blocked or page.fetch_status == "failed" for page in snapshot.pages)

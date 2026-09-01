from __future__ import annotations

from brand_ai_readiness.analysis.checks_crawl import crawl_findings
from brand_ai_readiness.analysis.snippet_policy import analyze_snippet_policy
from tests.helpers import page_from_html, snapshot_from_pages

HOME = "https://fixture.test/"
BODY = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Northwind Analytics</title>{meta}</head><body>
<h1>Operations reporting for logistics teams</h1>
<p>Northwind Analytics turns dispatch and shift data into same-day reports for
operations managers. Founded 2019, based in Leeds, serving regional carriers
across the United Kingdom and Ireland with shift-level analytics.</p>
{extra}</body></html>"""


def _page(meta: str = "", extra: str = "", headers: dict[str, str] | None = None, role="homepage"):
    page = page_from_html(HOME, BODY.format(meta=meta, extra=extra), role=role)
    page.headers = headers or {}
    return page


def _codes(pages):
    return {f.mechanism_code for f in crawl_findings(snapshot_from_pages(pages, start_url=HOME))}


# --- directive parsing ----------------------------------------------------


def test_nosnippet_detected_in_meta():
    policy = analyze_snippet_policy(HOME, '<meta name="robots" content="nosnippet">', {}, "nosnippet")
    assert policy.nosnippet and "meta robots" in policy.sources


def test_nosnippet_detected_in_header_only():
    """The case an HTML-only auditor cannot see at all."""
    policy = analyze_snippet_policy(HOME, "<html></html>", {"x-robots-tag": "nosnippet"}, None)
    assert policy.nosnippet
    assert "X-Robots-Tag header" in policy.sources


def test_header_name_is_matched_case_insensitively():
    policy = analyze_snippet_policy(HOME, "<html></html>", {"X-Robots-Tag": "noindex"}, None)
    assert policy.noindex_in_header


def test_unlimited_max_snippet_is_not_a_limit():
    """max-snippet:-1 means no limit and must never be reported."""
    policy = analyze_snippet_policy(HOME, "<html></html>", {}, "max-snippet:-1")
    assert policy.max_snippet == -1
    assert not policy.max_snippet_is_limiting


def test_low_max_snippet_is_a_limit():
    assert analyze_snippet_policy(HOME, "<html></html>", {}, "max-snippet:0").max_snippet_is_limiting
    assert analyze_snippet_policy(HOME, "<html></html>", {}, "max-snippet:20").max_snippet_is_limiting


def test_generous_max_snippet_is_not_a_limit():
    assert not analyze_snippet_policy(HOME, "<html></html>", {}, "max-snippet:320").max_snippet_is_limiting


def test_tightest_limit_wins_but_unlimited_overrides():
    both = analyze_snippet_policy(HOME, "<html></html>", {"x-robots-tag": "max-snippet:10"}, "max-snippet:200")
    assert both.max_snippet == 10
    unlimited = analyze_snippet_policy(HOME, "<html></html>", {"x-robots-tag": "max-snippet:-1"}, "max-snippet:10")
    assert not unlimited.max_snippet_is_limiting


def test_header_only_noindex_is_distinguished_from_declared_noindex():
    hidden = analyze_snippet_policy(HOME, "<html></html>", {"x-robots-tag": "noindex"}, None)
    assert hidden.header_only_noindex
    declared = analyze_snippet_policy(HOME, "<html></html>", {"x-robots-tag": "noindex"}, "noindex")
    assert not declared.header_only_noindex


# --- data-nosnippet -------------------------------------------------------


def test_targeted_data_nosnippet_is_not_flagged():
    """Wrapping a byline or a price is routine practice."""
    html = BODY.format(meta="", extra='<span data-nosnippet>By A. Reporter</span>')
    policy = analyze_snippet_policy(HOME, html, {}, None)
    assert policy.data_nosnippet_chars > 0
    assert not policy.data_nosnippet_dominant


def test_data_nosnippet_over_the_body_is_flagged():
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>T</title></head>'
        "<body><h1>Heading</h1><div data-nosnippet><p>"
        + ("The entire substance of this page is wrapped and cannot be quoted. " * 6)
        + "</p></div></body></html>"
    )
    policy = analyze_snippet_policy(HOME, html, {}, None)
    assert policy.data_nosnippet_dominant


# --- findings and their guards --------------------------------------------


def test_clean_page_produces_no_snippet_findings():
    codes = _codes([_page()])
    for code in (
        "nosnippet_suppresses_ai",
        "max_snippet_limits_ai",
        "data_nosnippet_hides_body",
        "noindex_header_only",
    ):
        assert code not in codes


def test_nosnippet_raises_a_finding():
    assert "nosnippet_suppresses_ai" in _codes([_page(meta='<meta name="robots" content="nosnippet">')])


def test_header_only_directives_raise_findings():
    codes = _codes([_page(headers={"x-robots-tag": "noindex, nosnippet"})])
    assert "nosnippet_suppresses_ai" in codes
    assert "noindex_header_only" in codes


def test_legal_and_account_pages_are_not_content_roles():
    """nosnippet on a terms page is ordinary practice, not a discoverability defect."""
    codes = _codes([_page(role="legal", meta='<meta name="robots" content="nosnippet">')])
    assert "nosnippet_suppresses_ai" not in codes


def test_unlimited_max_snippet_produces_no_finding():
    assert "max_snippet_limits_ai" not in _codes([_page(meta='<meta name="robots" content="max-snippet:-1">')])

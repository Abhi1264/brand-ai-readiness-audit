from __future__ import annotations

from brand_ai_readiness.analysis.checks_entity import entity_findings
from brand_ai_readiness.analysis.freshness import page_freshness
from brand_ai_readiness.orchestration.compose import enrich_snapshot
from tests.helpers import page_from_html, snapshot_from_site_dir


def test_publication_and_modification_dates():
    html = """<html><head>
      <meta property="article:published_time" content="2024-01-02">
      <meta property="article:modified_time" content="2024-06-01">
    </head><body><p>Published January 2, 2024. Updated June 1, 2024.</p></body></html>"""
    page = page_from_html("https://fixture.test/blog/a", html, role="article")
    signal = page_freshness(page)
    assert signal.date_published
    assert signal.date_modified
    assert signal.status != "stale_time_sensitive"


def test_copyright_year_is_not_modification_date():
    html = "<html><body><p>About our company. Copyright 2014. We make bolts.</p></body></html>"
    page = page_from_html("https://fixture.test/about", html, role="about")
    signal = page_freshness(page)
    assert signal.copyright_year == "2014"
    assert signal.status == "freshness_cannot_be_established"


def test_no_date_is_unknown_not_stale():
    html = "<html><body><h1>Docs</h1><p>Install the CLI and run the server.</p></body></html>"
    page = page_from_html("https://fixture.test/docs", html, role="docs")
    signal = page_freshness(page)
    assert signal.status == "freshness_cannot_be_established"


def test_stale_time_sensitive_pricing():
    snapshot = snapshot_from_site_dir("06_stale_content")
    enrich_snapshot(snapshot)
    codes = {item.mechanism_code for item in entity_findings(snapshot)}
    assert "stale_time_sensitive" in codes

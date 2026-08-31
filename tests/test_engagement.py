from __future__ import annotations

from brand_ai_readiness.analysis.checks_engagement import engagement_findings
from brand_ai_readiness.analysis.engagement import homepage_orientation, nav_quality
from brand_ai_readiness.models.snapshot import FetchedPage, RenderedPage
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from tests.helpers import page_from_html, snapshot_from_pages, snapshot_from_site_dir


def test_clear_cta_on_excellent_homepage():
    snapshot = snapshot_from_site_dir("01_excellent")
    home = snapshot.homepage()
    assert home
    orient = homepage_orientation(home)
    assert orient["has_h1"]
    assert orient["cta_texts"]


def test_absent_cta_and_orientation_on_weak_engagement_site():
    snapshot = snapshot_from_site_dir("10_strong_disco_weak_engagement")
    codes = {item.mechanism_code for item in engagement_findings(snapshot)}
    assert "weak_homepage_orientation" in codes


def test_confusing_labels_and_dead_end():
    snapshot = snapshot_from_site_dir("09_broken_navigation")
    home = snapshot.homepage()
    assert home
    _count, confusing = nav_quality(home)
    assert confusing
    codes = {item.mechanism_code for item in engagement_findings(snapshot)}
    assert "confusing_nav_labels" in codes
    assert "dead_end_pages" in codes


def test_broken_links_finding():
    home = page_from_html(
        "https://fixture.test/",
        '<html><body><nav><a href="/gone">Products</a></nav><h1>Hi</h1><p>We are X. Get started.</p></body></html>',
        role="homepage",
    )
    home.internal_links.append("https://fixture.test/gone")
    broken = FetchedPage(
        url="https://fixture.test/gone",
        final_url="https://fixture.test/gone",
        status_code=404,
        fetch_status="failed",
        error="http_404",
        role="product",
    )
    snapshot = snapshot_from_pages([home, broken], start_url="https://fixture.test/")
    codes = {item.mechanism_code for item in engagement_findings(snapshot)}
    assert "broken_internal_links" in codes


def test_mobile_issue_from_rendered_metrics():
    home = page_from_html(
        "https://fixture.test/",
        "<html><body><h1>Hi</h1><p>We are MobileCo. Get started for teams.</p></body></html>",
        role="homepage",
    )
    rendered = [
        RenderedPage(url=home.url, viewport="desktop", cta_visible=True, nav_visible=True, overflow_x=False),
        RenderedPage(url=home.url, viewport="mobile", cta_visible=False, nav_visible=False, overflow_x=True, min_font_px=9),
    ]
    snapshot = snapshot_from_pages([home], start_url="https://fixture.test/", rendered=rendered)
    snapshot.stats.rendering_status = "complete"
    codes = {item.mechanism_code for item in engagement_findings(snapshot)}
    assert "mobile_engagement_blocker" in codes


def test_strong_engagement_weak_discoverability_site():
    snapshot = snapshot_from_site_dir("11_weak_disco_strong_engagement")
    report = report_from_snapshot(snapshot)
    codes = {item.category for item in report.findings}
    assert "engagement" not in {f.category for f in report.findings if f.severity in {"critical", "high"}}
    assert any(item.category == "crawlability" or item.category == "structured_data" for item in report.findings)
    assert "noindex_important" in {getattr(item, "category", "") for item in report.findings} or any(
        "noindex" in item.title.lower() for item in report.findings
    )
    _ = codes

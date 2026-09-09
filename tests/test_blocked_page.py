from __future__ import annotations

from brand_ai_readiness.analysis.blocked_page import (
    assess_block,
    homepage_content_unusable,
)
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from tests.helpers import page_from_html, snapshot_from_pages, snapshot_from_site_dir

HOME = "https://fixture.test/"
REAL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Meridian Freight</title></head><body><nav aria-label="Primary"><a href="/">Home</a></nav>
<h1>Same-day pallet delivery across the Midlands</h1>
<p>Meridian Freight has moved palletised goods for regional manufacturers since 2011,
operating 34 vehicles from depots in Birmingham, Coventry and Derby.</p>
<a href="/pricing">See full pricing</a></body></html>"""
DENIED = """<!doctype html><html><head><title>Access Denied</title></head>
<body><h1>Access Denied</h1><p>You don't have permission to access this resource.</p></body></html>"""


def _assess(html, *, status=200, title=None, words=40, headers=None):
    return assess_block(
        status_code=status, html=html, text=html, title=title, word_count=words, headers=headers or {}
    )


# --- detection ------------------------------------------------------------


def test_vendor_marker_alone_is_enough():
    assert _assess('<html><body><div class="cf-browser-verification"></div></body></html>').is_blocked


def test_edge_header_alone_is_enough():
    assert _assess("<html></html>", headers={"cf-mitigated": "challenge"}).is_blocked


def test_challenge_wording_with_a_blocking_status():
    assert _assess(DENIED, status=403, title="Access Denied", words=12).is_blocked


def test_challenge_wording_with_an_empty_body():
    assert _assess(DENIED, status=200, title="Access Denied", words=12).is_blocked


# --- false-positive guards ------------------------------------------------


def test_ordinary_page_is_not_a_challenge():
    assert not _assess(REAL, title="Meridian Freight", words=45).is_blocked


def test_article_about_access_denial_is_not_a_challenge():
    """Wording alone must not convict a page that was actually served."""
    html = (
        "<html><head><title>Why you keep seeing Access Denied errors</title></head><body>"
        "<h1>Why you keep seeing Access Denied errors</h1><p>" + ("Explanatory prose. " * 60)
        + "</p></body></html>"
    )
    assert not _assess(html, status=200, title="Why you keep seeing Access Denied errors", words=180).is_blocked


def test_a_plain_403_without_challenge_signals_is_not_convicted():
    """One permission-protected URL is not evidence of a bot wall."""
    html = "<html><head><title>Members area</title></head><body><p>" + ("Sign in required. " * 40) + "</p></body></html>"
    assert not _assess(html, status=403, title="Members area", words=120).is_blocked


# --- what the orchestrator does with it -----------------------------------


def test_served_homepage_is_analysed_normally():
    snapshot = snapshot_from_pages([page_from_html(HOME, REAL, role="homepage")], start_url=HOME)
    assert homepage_content_unusable(snapshot) is None


def test_thin_but_served_homepage_is_still_analysed():
    """A 4-word homepage is a real engagement defect, not a fetch failure.

    Suppressing it would hide exactly the problem the audit exists to find.
    """
    snapshot = snapshot_from_site_dir("10_strong_disco_weak_engagement")
    assert homepage_content_unusable(snapshot) is None
    assert any(f.category == "engagement" for f in report_from_snapshot(snapshot).findings)


def test_unfetched_homepage_reports_the_reason():
    page = page_from_html(HOME, "Not found", status_code=404, role="homepage")
    snapshot = snapshot_from_pages([page], start_url=HOME)
    reason = homepage_content_unusable(snapshot)
    assert reason and "404" in reason


def test_content_skills_are_skipped_and_the_report_says_so():
    page = page_from_html(HOME, DENIED, status_code=403, role="homepage")
    snapshot = snapshot_from_pages([page], start_url=HOME)
    report = report_from_snapshot(snapshot)
    categories = {f.category for f in report.findings}
    # Nothing may be asserted about content the site never served.
    assert not categories & {"structured_data", "entity", "engagement", "freshness"}
    assert any("were skipped because" in line for line in report.coverage.limitations)

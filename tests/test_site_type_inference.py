from __future__ import annotations

from brand_ai_readiness.analysis.site_type import expected_schema_types, infer_site_type
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.crawler.crawler import BoundedCrawler
from brand_ai_readiness.crawler.priority import classify_role
from tests.helpers import page_from_html, snapshot_from_pages

HOME = "https://fixture.test/"
BODY = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>T</title></head>
<body><h1>Heading</h1><p>Some ordinary body copy for the page.</p></body></html>"""


# --- role classification --------------------------------------------------


def test_role_word_midpath_is_a_facet_not_a_page():
    """A job board's location filters are not contact pages."""
    assert classify_role("https://x.test/jobs/location/warsaw-poland/") == "other"
    assert classify_role("https://x.test/jobs/location/telecommute") == "other"


def test_locations_section_only_counts_at_top_level():
    assert classify_role("https://x.test/locations") == "contact"
    assert classify_role("https://x.test/locations/boston") == "contact"
    assert classify_role("https://x.test/jobs/locations") == "other"


def test_first_and_last_segment_roles_still_resolve():
    assert classify_role("https://x.test/products/widget") == "product"
    assert classify_role("https://x.test/en/contact") == "contact"
    assert classify_role("https://x.test/about/apps") == "about"
    assert classify_role("https://x.test/blog/2024/a-post") == "article"
    assert classify_role("https://x.test/") == "homepage"


# --- site-type inference --------------------------------------------------


DOCS_HOME = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Platform documentation</title></head><body><h1>Documentation</h1>
<p>Getting started guides and the API reference for the platform.</p></body></html>"""


def _snapshot_with_roles(roles: list[str], home_html: str = BODY):
    pages = [page_from_html(HOME, home_html, role="homepage")]
    for index, role in enumerate(roles):
        pages.append(page_from_html(f"{HOME}p{index}", BODY, role=role))  # type: ignore[arg-type]
    return snapshot_from_pages(pages, start_url=HOME)


def test_one_large_role_family_cannot_outvote_a_competing_signal():
    """The python.org regression.

    30 location-ish pages plus documentation vocabulary on the homepage. Each
    contact page used to add a point, so the family scored 30 against docs' 2
    and every such site was classified local_business — which then recommended
    LocalBusiness JSON-LD. The family now scores once, so it cannot bury a
    genuine competing signal.
    """
    snapshot = _snapshot_with_roles(["contact"] * 30, home_html=DOCS_HOME)
    infer_site_type(snapshot)
    assert snapshot.site_type != "local_business"
    assert "LocalBusiness" not in expected_schema_types(snapshot.site_type)


def test_a_genuinely_local_site_is_still_local():
    """Guard against over-correcting: real local signals must still land."""
    local_home = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Bakery</title></head><body><h1>Visit us</h1>"
        "<p>Opening hours, directions, and reservations for our shop.</p></body></html>"
    )
    snapshot = _snapshot_with_roles(["contact", "contact"], home_html=local_home)
    infer_site_type(snapshot)
    assert snapshot.site_type == "local_business"


def test_narrow_winner_is_reported_as_mixed():
    snapshot = _snapshot_with_roles(["docs", "article"])
    infer_site_type(snapshot)
    assert snapshot.site_type == "mixed"
    # A mixed site must not be handed a specialised schema expectation.
    assert "LocalBusiness" not in expected_schema_types(snapshot.site_type)


def test_clear_signal_still_wins():
    snapshot = _snapshot_with_roles(["product", "product", "pricing"])
    infer_site_type(snapshot)
    assert snapshot.site_type in {"ecommerce", "mixed"}


def test_site_type_signals_state_the_page_counts():
    snapshot = _snapshot_with_roles(["docs", "docs"])
    infer_site_type(snapshot)
    assert any("crawled pages" in signal for signal in snapshot.site_type_signals)


# --- crawl diversity ------------------------------------------------------


def test_deep_url_family_is_capped():
    budget = AuditBudget(max_pages=40, max_pages_per_url_family=8, enable_render=False)
    crawler = BoundedCrawler(HOME, budget)
    for index in range(30):
        crawler.enqueue(f"{HOME}jobs/location/city-{index}")
    assert len(crawler._enqueued) == 8


def test_top_level_sections_are_not_capped():
    """/products/* and locale prefixes are what an audit wants; leave them alone."""
    budget = AuditBudget(max_pages=40, max_pages_per_url_family=8, enable_render=False)
    crawler = BoundedCrawler(HOME, budget)
    for index in range(20):
        crawler.enqueue(f"{HOME}products/item-{index}")
    assert len(crawler._enqueued) == 20


def test_cap_is_per_family_not_global():
    budget = AuditBudget(max_pages=40, max_pages_per_url_family=2, enable_render=False)
    crawler = BoundedCrawler(HOME, budget)
    for index in range(5):
        crawler.enqueue(f"{HOME}jobs/location/city-{index}")
        crawler.enqueue(f"{HOME}docs/api/page-{index}")
    assert len(crawler._enqueued) == 4  # 2 from each of the two families

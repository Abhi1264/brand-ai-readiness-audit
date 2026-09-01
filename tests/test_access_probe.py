from __future__ import annotations

from brand_ai_readiness.analysis.checks_crawl import crawl_findings
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.crawler.crawler import crawl_site_sync
from brand_ai_readiness.models.snapshot import AccessProbeResult, CrawlSnapshot
from brand_ai_readiness.scoring.scorecard import compute_scorecard
from tests.helpers import page_from_html, snapshot_from_pages

HOME = "https://fixture.test/"
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Northwind Analytics</title><meta name="viewport" content="width=device-width">
</head><body><nav aria-label="Primary"><a href="/">Home</a></nav>
<h1>Operations reporting</h1><p>Shift-level reporting for logistics teams.</p>
<a href="/about">About the pipeline</a></body></html>"""


def _snapshot(probes: list[AccessProbeResult], *, robots_raw: str | None = None) -> CrawlSnapshot:
    snapshot = snapshot_from_pages(
        [page_from_html(HOME, PAGE, role="homepage")], start_url=HOME, robots_raw=robots_raw
    )
    snapshot.access_probes = probes
    snapshot.access_probe_status = "complete"
    # Default to a readable robots.txt: the robots-vs-server table only means
    # anything when the declared policy was actually retrievable. Tests that
    # exercise the unreadable case set this back to False explicitly.
    snapshot.robots.available = True
    return snapshot


def _probe(agent: str, status: int, *, ai: bool = True, robots_allows: bool = True, body: int = 900):
    return AccessProbeResult(
        agent=agent,
        user_agent=f"test/{agent}",
        is_ai_crawler=ai,
        status_code=status,
        method="HEAD",
        body_bytes=body,
        robots_allows=robots_allows,
    )


def _codes(snapshot: CrawlSnapshot) -> set[str]:
    return {item.mechanism_code for item in crawl_findings(snapshot)}


# --- the four cells of the robots-vs-server table -------------------------


def test_robots_allows_but_server_blocks_is_critical():
    """The divergent cell: robots.txt says yes, the edge says no."""
    snapshot = _snapshot(
        [
            _probe("browser", 200, ai=False),
            _probe("GPTBot", 403, robots_allows=True),
            _probe("ClaudeBot", 403, robots_allows=True),
        ]
    )
    findings = [f for f in crawl_findings(snapshot) if f.mechanism_code == "ai_crawler_edge_blocked"]
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert "GPTBot" in findings[0].suggested_action.summary


def test_robots_blocks_and_server_blocks_is_policy_not_defect():
    """The consistent cell: deliberate exclusion, reported at lower severity."""
    snapshot = _snapshot(
        [
            _probe("browser", 200, ai=False),
            _probe("GPTBot", 403, robots_allows=False),
        ]
    )
    findings = [
        f for f in crawl_findings(snapshot) if f.mechanism_code == "ai_crawler_excluded_by_policy"
    ]
    assert len(findings) == 1
    assert findings[0].severity in {"medium", "low"}
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)


def test_robots_blocks_but_server_allows_emits_no_probe_finding():
    """No 4xx means the probe has nothing to report, whatever robots.txt says."""
    snapshot = _snapshot(
        [
            _probe("browser", 200, ai=False),
            _probe("GPTBot", 200, robots_allows=False),
        ]
    )
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)
    assert "ai_crawler_excluded_by_policy" not in _codes(snapshot)


def test_everyone_allowed_emits_nothing():
    snapshot = _snapshot(
        [
            _probe("browser", 200, ai=False),
            _probe("GPTBot", 200),
            _probe("ClaudeBot", 200),
        ]
    )
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)


# --- false-positive guards ------------------------------------------------


def test_paywalled_origin_is_not_an_ai_crawler_finding():
    """If the browser is refused too, this is not bot policy."""
    snapshot = _snapshot(
        [
            _probe("browser", 401, ai=False),
            _probe("GPTBot", 401),
        ]
    )
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)


def test_body_length_difference_alone_does_not_trigger():
    """Personalization and A/B tests move body size without any bot policy."""
    snapshot = _snapshot(
        [
            _probe("browser", 200, ai=False, body=40000),
            _probe("GPTBot", 200, body=900),
        ]
    )
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)


def test_incomplete_probe_is_never_evidence():
    snapshot = _snapshot([_probe("browser", 200, ai=False), _probe("GPTBot", 403)])
    snapshot.access_probe_status = "unavailable"
    assert "ai_crawler_edge_blocked" not in _codes(snapshot)


def test_probe_finding_is_suppressed_when_robots_already_flagged():
    """A site that blocks our own crawler too is covered by the robots finding."""
    robots = "User-agent: *\nDisallow: /\n"
    page = page_from_html(HOME, PAGE, role="homepage", robots_blocked=True)
    snapshot = snapshot_from_pages([page], start_url=HOME, robots_raw=robots)
    snapshot.access_probes = [
        _probe("browser", 200, ai=False),
        _probe("GPTBot", 403, robots_allows=False),
    ]
    snapshot.access_probe_status = "complete"
    codes = _codes(snapshot)
    assert "robots_blocks_important" in codes
    assert "ai_crawler_excluded_by_policy" not in codes


# --- scoring ---------------------------------------------------------------


def test_blocked_ai_crawlers_cap_crawlability_score():
    open_site = _snapshot([_probe("browser", 200, ai=False), _probe("GPTBot", 200)])
    blocked_site = _snapshot(
        [
            _probe("browser", 200, ai=False),
            _probe("GPTBot", 403),
            _probe("ClaudeBot", 403),
        ]
    )
    assert compute_scorecard(open_site).components["crawlability"] == 100
    assert compute_scorecard(blocked_site).components["crawlability"] <= 30


# --- live probe mechanics against a local UA-gated server -------------------


def test_probe_detects_ua_gating_end_to_end(serve_ua_gated_site):
    url = serve_ua_gated_site("12_ua_gated", ("GPTBot",))
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=3, enable_render=False))

    assert snapshot.access_probe_status == "complete"
    by_agent = {probe.agent: probe for probe in snapshot.access_probes}
    assert by_agent["browser"].status_code == 200
    assert by_agent["GPTBot"].status_code == 403
    assert by_agent["ClaudeBot"].status_code == 200

    findings = [f for f in crawl_findings(snapshot) if f.mechanism_code == "ai_crawler_edge_blocked"]
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert "GPTBot" in findings[0].evidence.as_text()
    # ClaudeBot was served normally and must not be named as blocked.
    assert "ClaudeBot" not in findings[0].suggested_action.summary


def test_probe_does_not_fetch_pages_or_alter_crawl(serve_ua_gated_site):
    url = serve_ua_gated_site("12_ua_gated", ("GPTBot",))
    snapshot = crawl_site_sync(url, AuditBudget(max_pages=3, enable_render=False))
    # Probes are diagnostics, not crawled pages.
    assert all(page.status_code != 403 for page in snapshot.pages)
    assert snapshot.stats.pages_crawled >= 1


def test_probe_can_be_disabled(serve_ua_gated_site):
    url = serve_ua_gated_site("12_ua_gated", ("GPTBot",))
    snapshot = crawl_site_sync(
        url, AuditBudget(max_pages=3, enable_render=False, enable_access_probe=False)
    )
    assert snapshot.access_probe_status == "skipped"
    assert snapshot.access_probes == []
    assert "ai_crawler_edge_blocked" not in {f.mechanism_code for f in crawl_findings(snapshot)}


# --- the probe must not cost more than the crawl it informs -----------------


def test_probe_budget_fails_fast():
    """Origins that tarpit unfamiliar agents must not blow the time budget.

    Without this the probe inherits the crawl's retries and timeout, so one
    hanging origin costs retries x timeout x (HEAD then GET) per agent.
    """
    from brand_ai_readiness.crawler.access_probe import _probe_budget

    slow = AuditBudget(request_timeout_s=15.0, max_retries=2)
    probe = _probe_budget(slow)
    assert probe.max_retries == 0
    assert probe.request_timeout_s <= 8.0
    # The crawl's own budget must be untouched.
    assert slow.max_retries == 2 and slow.request_timeout_s == 15.0


def test_probe_status_reaches_the_report():
    """A reader must be able to tell whether the probe actually ran."""
    from brand_ai_readiness.orchestration.compose import report_from_snapshot

    snapshot = _snapshot([_probe("browser", 200, ai=False), _probe("GPTBot", 200)])
    report = report_from_snapshot(snapshot)
    assert report.coverage.access_probe_status == "complete"

    unknown = _snapshot([_probe("browser", 200, ai=False)])
    unknown.access_probe_status = "unavailable"
    degraded = report_from_snapshot(unknown)
    assert degraded.coverage.access_probe_status == "unavailable"
    assert any("access probe" in line.lower() for line in degraded.coverage.limitations)


def test_unreadable_robots_is_not_reported_as_permission():
    """Absence of robots.txt is not the same claim as robots.txt permitting an agent."""
    snapshot = _snapshot(
        [_probe("browser", 200, ai=False), _probe("GPTBot", 403, robots_allows=True)]
    )
    snapshot.robots.available = False
    findings = crawl_findings(snapshot)
    codes = {f.mechanism_code for f in findings}
    assert "ai_crawler_edge_blocked" not in codes
    assert "ai_crawler_blocked_robots_unknown" in codes
    reported = [f for f in findings if f.mechanism_code == "ai_crawler_blocked_robots_unknown"][0]
    assert reported.severity != "critical"
    assert "permits" not in reported.evidence.as_text()


def test_readable_robots_still_yields_the_critical_contradiction():
    snapshot = _snapshot(
        [_probe("browser", 200, ai=False), _probe("GPTBot", 403, robots_allows=True)]
    )
    snapshot.robots.available = True
    findings = [f for f in crawl_findings(snapshot) if f.mechanism_code == "ai_crawler_edge_blocked"]
    assert len(findings) == 1 and findings[0].severity == "critical"

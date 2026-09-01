from __future__ import annotations

from brand_ai_readiness.analysis.engagement import EngagementSignals, analyze_engagement
from brand_ai_readiness.analysis.structured import jsonld_types_on
from brand_ai_readiness.models.report import Scorecard
from brand_ai_readiness.models.snapshot import CrawlSnapshot


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def compute_scorecard(
    snapshot: CrawlSnapshot, signals: EngagementSignals | None = None
) -> Scorecard:
    pages = snapshot.successful_pages()
    n = max(len(pages), 1)
    blocked = snapshot.stats.pages_blocked
    failed = snapshot.stats.pages_failed
    crawlability = 100
    if snapshot.robots.available and blocked:
        crawlability -= min(50, int(40 * blocked / max(n + blocked, 1)) + 15)
    if failed:
        crawlability -= min(30, failed * 8)
    important_fail = [
        page
        for page in snapshot.pages
        if page.role in {"homepage", "product", "about"} and page.fetch_status == "failed"
    ]
    if any(page.role == "homepage" and page.fetch_status == "failed" for page in important_fail):
        crawlability = min(crawlability, 25)
    # An origin that refuses AI SEARCH crawlers is not crawlable by the systems
    # this audit is about, however healthy it looks to the audit's own
    # user-agent. Training-class blocks are a licensing choice and are not
    # scored -- penalising them would mark a supported configuration as broken.
    browser_probe = snapshot.browser_probe()
    if browser_probe is not None and browser_probe.reachable():
        blocked_agents = [probe for probe in snapshot.search_probes() if probe.status_code >= 400]
        if blocked_agents:
            crawlability = min(crawlability, 30 if len(blocked_agents) > 1 else 55)

    low_text = sum(1 for page in pages if page.word_count < 25)
    machine = 100 - min(55, low_text * 15)
    if snapshot.stats.rendering_status == "unavailable":
        machine = max(machine - 5, 40)

    typed = jsonld_types_on(snapshot)
    structured = 35
    if typed:
        structured = 55 + min(45, 10 * len(typed))
    og = any(block.kind == "opengraph" for block in snapshot.structured)
    if og:
        structured = min(100, structured + 10)
    if any(block.parse_error for block in snapshot.structured if block.kind == "jsonld"):
        structured = max(20, structured - 20)

    entity = 50
    if snapshot.entities:
        entity = 70
    if any(item.kind in {"organization", "brand"} for item in snapshot.entities):
        entity = 80
    if any(item.same_as for item in snapshot.entities):
        entity = min(100, entity + 10)

    dated = 40
    homepage = snapshot.homepage()
    if homepage and ("20" in (homepage.text or "") or "updated" in (homepage.text or "").lower()):
        dated = 65
    if any("dateModified" in (block.data.keys()) for block in snapshot.structured):
        dated = 80

    eng = signals or analyze_engagement(snapshot)
    orientation = 20
    if eng.has_h1:
        orientation += 25
    if eng.identity_statement:
        orientation += 25
    if eng.audience_statement:
        orientation += 15
    if homepage and homepage.word_count >= 40:
        orientation += 15
    navigation = 40 + min(40, eng.nav_count * 8)
    if eng.confusing_labels:
        navigation -= 20
    cta = 25 + min(50, len(eng.cta_texts) * 20)
    linking = 80
    if eng.dead_end_urls:
        linking -= min(40, 12 * len(eng.dead_end_urls))
    if eng.broken_internal:
        linking -= min(40, 15 * len(eng.broken_internal))
    mobile = 75
    if snapshot.stats.rendering_status in {"unavailable", "skipped"}:
        mobile = 60
    if eng.mobile_issues:
        mobile = max(20, 80 - 20 * len(eng.mobile_issues))

    components = {
        "crawlability": _clamp(crawlability),
        "machine_readability": _clamp(machine),
        "structured_data": _clamp(structured),
        "entity_clarity": _clamp(entity),
        "freshness_transparency": _clamp(dated),
        "homepage_orientation": _clamp(orientation),
        "navigation": _clamp(navigation),
        "cta_clarity": _clamp(cta),
        "internal_linking": _clamp(linking),
        "mobile": _clamp(mobile),
    }
    ai = round(
        0.30 * components["crawlability"]
        + 0.25 * components["machine_readability"]
        + 0.25 * components["structured_data"]
        + 0.12 * components["entity_clarity"]
        + 0.08 * components["freshness_transparency"]
    )
    engagement = round(
        0.30 * components["homepage_orientation"]
        + 0.20 * components["navigation"]
        + 0.20 * components["cta_clarity"]
        + 0.15 * components["internal_linking"]
        + 0.15 * components["mobile"]
    )
    overall = round(0.55 * ai + 0.45 * engagement)
    return Scorecard(
        ai_discoverability_score=_clamp(ai),
        engagement_score=_clamp(engagement),
        overall_score=_clamp(overall),
        components=components,
        formula=(
            "ai=0.30*crawlability+0.25*machine_readability+0.25*structured_data"
            "+0.12*entity_clarity+0.08*freshness_transparency; "
            "engagement=0.30*homepage_orientation+0.20*navigation+0.20*cta_clarity"
            "+0.15*internal_linking+0.15*mobile; overall=0.55*ai+0.45*engagement"
        ),
    )

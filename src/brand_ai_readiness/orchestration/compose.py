from __future__ import annotations

import logging
from datetime import datetime, timezone

from brand_ai_readiness.analysis.checks_crawl import crawl_findings
from brand_ai_readiness.analysis.checks_engagement import engagement_findings
from brand_ai_readiness.analysis.checks_entity import entity_findings
from brand_ai_readiness.analysis.checks_structured import structured_findings
from brand_ai_readiness.analysis.claims import extract_claims
from brand_ai_readiness.analysis.engagement import EngagementSignals, analyze_engagement
from brand_ai_readiness.analysis.entities import extract_entities
from brand_ai_readiness.analysis.site_type import infer_site_type
from brand_ai_readiness.analysis.structured import collect_structured
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.analysis.html import extract_links, parse_html
from brand_ai_readiness.crawler.crawler import crawl_additional, crawl_site
from brand_ai_readiness.models.findings import Finding, PublicFinding
from brand_ai_readiness.models.report import AuditReport, Coverage, SeveritySummary
from brand_ai_readiness.models.snapshot import CrawlSnapshot
from brand_ai_readiness.orchestration.dedupe import dedupe_findings
from brand_ai_readiness.orchestration.llm import maybe_polish
from brand_ai_readiness.orchestration.proactive import proactive_recommendations
from brand_ai_readiness.rendering.renderer import render_snapshot_pages_async
from brand_ai_readiness.scoring.prioritize import sort_findings
from brand_ai_readiness.scoring.scorecard import compute_scorecard
from brand_ai_readiness.scoring.severity import apply_severity

logger = logging.getLogger(__name__)


def enrich_snapshot(snapshot: CrawlSnapshot) -> CrawlSnapshot:
    infer_site_type(snapshot)
    collect_structured(snapshot)
    extract_entities(snapshot)
    extract_claims(snapshot)
    return snapshot


def collect_skill_findings(
    snapshot: CrawlSnapshot, signals: EngagementSignals | None = None
) -> list[Finding]:
    signals = signals or analyze_engagement(snapshot)
    buckets = [
        ("crawl-render-audit", crawl_findings),
        ("structured-data-audit", structured_findings),
        ("freshness-entity-audit", entity_findings),
        ("engagement-audit", lambda snap: engagement_findings(snap, signals)),
    ]
    collected: list[Finding] = []
    for name, fn in buckets:
        try:
            collected.extend(fn(snapshot))
        except Exception as exc:  # noqa: BLE001 — one skill must not abort the report
            logger.warning("skill %s failed: %s", name, exc)
    return collected


def _coverage(snapshot: CrawlSnapshot) -> Coverage:
    limits: list[str] = []
    if snapshot.stats.rendering_status in {"unavailable", "skipped"}:
        limits.append(
            f"Browser rendering was {snapshot.stats.rendering_status}; raw-vs-rendered gaps may be under-counted."
        )
    if snapshot.stats.pages_failed:
        limits.append(f"{snapshot.stats.pages_failed} page(s) failed to fetch.")
    if snapshot.corroboration_status == "unavailable":
        limits.append("Independent corroboration was not run (corroboration_status=unavailable).")
    if snapshot.access_probe_status not in {"complete"}:
        limits.append(
            f"AI-crawler access probe was {snapshot.access_probe_status}; whether AI crawlers are "
            "served the same content as a browser could not be established."
        )
    if snapshot.stats.pages_crawled < snapshot.stats.pages_discovered:
        limits.append(
            f"Crawl budget stopped at {snapshot.stats.pages_crawled} of {snapshot.stats.pages_discovered} discovered URLs."
        )
    return Coverage(
        pages_discovered=snapshot.stats.pages_discovered,
        pages_crawled=snapshot.stats.pages_crawled,
        pages_rendered=snapshot.stats.pages_rendered,
        pages_failed=snapshot.stats.pages_failed,
        pages_blocked=snapshot.stats.pages_blocked,
        rendering_status=snapshot.stats.rendering_status,
        corroboration_status=snapshot.corroboration_status,
        access_probe_status=snapshot.access_probe_status,
        limitations=limits,
    )


def build_report(
    snapshot: CrawlSnapshot,
    findings: list[Finding],
    signals: EngagementSignals | None = None,
) -> AuditReport:
    findings = [apply_severity(item) for item in findings]
    findings = dedupe_findings(findings)
    findings = sort_findings(findings)
    public: list[PublicFinding] = []
    for index, finding in enumerate(findings, start=1):
        payload = finding.public_dict(f"F-{index:03d}")
        public.append(PublicFinding.model_validate(payload))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in public:
        counts[item.severity] += 1
    summary = SeveritySummary(
        total_findings=len(public),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
    )
    return AuditReport(
        site=snapshot.site,
        audited_at=datetime.now(timezone.utc),
        summary=summary,
        findings=public,
        proactive_recommendations=proactive_recommendations(snapshot, findings),
        crawl_statistics=snapshot.stats.model_dump(),
        coverage=_coverage(snapshot),
        scores=compute_scorecard(snapshot, signals),
        site_type=snapshot.site_type,
    )


async def _expand_from_rendered(snapshot: CrawlSnapshot, budget: AuditBudget) -> CrawlSnapshot:
    seen = {page.url for page in snapshot.pages} | {page.final_url for page in snapshot.pages}
    seeds: list[str] = []
    for item in snapshot.rendered:
        if item.error or item.viewport != "desktop" or not item.html:
            continue
        internal, _external = extract_links(parse_html(item.html), item.url)
        for link in internal:
            if link not in seen:
                seeds.append(link)
        for page in snapshot.pages:
            if page.url == item.url or page.final_url == item.url:
                merged = list(dict.fromkeys(page.internal_links + internal))
                page.internal_links = merged
    extra = await crawl_additional(snapshot.start_url, seeds, budget, seen)
    if extra:
        snapshot.pages.extend(extra)
        snapshot.stats.pages_crawled = len(snapshot.successful_pages())
        snapshot.stats.pages_failed = sum(1 for page in snapshot.pages if page.fetch_status == "failed")
        snapshot.stats.pages_discovered = max(snapshot.stats.pages_discovered, len(snapshot.pages) + len(seeds))
    return snapshot


async def run_audit(url: str, budget: AuditBudget | None = None) -> AuditReport:
    budget = budget or AuditBudget()
    snapshot = await crawl_site(url, budget)
    try:
        await render_snapshot_pages_async(snapshot, budget)
        if snapshot.stats.rendering_status in {"complete", "partial"}:
            snapshot = await _expand_from_rendered(snapshot, budget)
    except Exception as exc:  # noqa: BLE001
        logger.info("rendering skipped: %s", exc)
        snapshot.stats.rendering_status = "unavailable"
    enrich_snapshot(snapshot)
    signals = analyze_engagement(snapshot)
    findings = collect_skill_findings(snapshot, signals)
    findings = maybe_polish(findings, budget.enable_llm_polish)
    return build_report(snapshot, findings, signals)


def report_from_snapshot(snapshot: CrawlSnapshot) -> AuditReport:
    enrich_snapshot(snapshot)
    signals = analyze_engagement(snapshot)
    return build_report(snapshot, collect_skill_findings(snapshot, signals), signals)

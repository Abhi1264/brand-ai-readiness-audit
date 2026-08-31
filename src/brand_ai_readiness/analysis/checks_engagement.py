"""Engagement, orientation, continuation, and mobile findings."""

from __future__ import annotations

from brand_ai_readiness.analysis.engagement import EngagementSignals, analyze_engagement
from brand_ai_readiness.analysis.pageview import effective_page
from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.snapshot import CrawlSnapshot


def engagement_findings(
    snapshot: CrawlSnapshot, signals: EngagementSignals | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    signals = signals or analyze_engagement(snapshot)
    homepage = snapshot.homepage()
    if homepage:
        homepage = effective_page(homepage, snapshot)
    pages = snapshot.successful_pages()
    n = max(len(pages), 1)

    if homepage:
        missing_bits = []
        if not signals.has_h1:
            missing_bits.append("no H1")
        if not signals.identity_statement:
            missing_bits.append("no identity statement (who/what)")
        if not signals.cta_texts:
            missing_bits.append("no recognizable CTA phrasing")
        if homepage.word_count < 20:
            missing_bits.append(f"only {homepage.word_count} visible words")
        if len(missing_bits) >= 2:
            findings.append(
                make_finding(
                    id="EG-001",
                    category="engagement",
                    title="Homepage does not orient a first-time visitor",
                    mechanism_code="weak_homepage_orientation",
                    mechanism="Visitors (and machines summarizing the homepage) need a named entity, an offer, and a next action above the fold.",
                    impact="People bounce; assistants extract an empty or generic description.",
                    observation=(
                        f"Homepage orientation gaps: {', '.join(missing_bits)}. "
                        f"H1={signals.h1_text!r}; CTA matches={signals.cta_texts or 'none'}."
                    ),
                    source_urls=[homepage.url],
                    metrics={
                        "has_h1": signals.has_h1,
                        "h1_text": signals.h1_text,
                        "identity_statement": signals.identity_statement,
                        "audience_statement": signals.audience_statement,
                        "cta_texts": signals.cta_texts,
                        "word_count": homepage.word_count,
                    },
                    action_summary="Add a specific H1, one sentence on who the site is for, and one primary CTA on the homepage.",
                    implementation_direction="Lead with [brand] + [offer] + [audience], then one button to the main conversion path.",
                    confidence=0.8,
                    scope_pages=1,
                    scope_fraction=0.5,
                    impact_weight=3,
                )
            )
        elif not signals.audience_statement and snapshot.site_type in {"saas", "ecommerce", "nonprofit"}:
            findings.append(
                make_finding(
                    id="EG-002",
                    category="engagement",
                    title="Homepage never states who the offering is for",
                    mechanism_code="missing_audience",
                    mechanism="Without an audience phrase, visitors cannot self-qualify and assistants omit the 'for whom' clause.",
                    impact="Weaker engagement and weaker citations in 'best X for Y' questions.",
                    observation="No 'for <audience>' / 'built for' phrasing was observed on the homepage.",
                    source_urls=[homepage.url],
                    metrics={"site_type": snapshot.site_type, "h1": signals.h1_text},
                    action_summary="Add one clause naming the intended customer or visitor on the homepage.",
                    confidence=0.68,
                    scope_pages=1,
                    scope_fraction=0.3,
                    impact_weight=1,
                )
            )

    if signals.confusing_labels:
        findings.append(
            make_finding(
                id="EG-003",
                category="engagement",
                title="Navigation uses non-descriptive labels",
                mechanism_code="confusing_nav_labels",
                mechanism="Labels like 'click here' do not tell a visitor or a crawler what the destination is.",
                impact="Next-step choice is slower and link text is a weak relevance signal.",
                observation=f"Observed weak nav labels: {signals.confusing_labels}.",
                source_urls=[homepage.url] if homepage else [],
                metrics={"labels": signals.confusing_labels, "nav_count": signals.nav_count},
                quotes=signals.confusing_labels[:4],
                action_summary="Replace generic labels with destination words (Pricing, Docs, Contact, Product name).",
                confidence=0.85,
                scope_pages=1,
                scope_fraction=0.3,
                impact_weight=1,
            )
        )

    if signals.dead_end_urls:
        findings.append(
            make_finding(
                id="EG-004",
                category="engagement",
                title="Important pages are dead ends with almost no onward internal links",
                mechanism_code="dead_end_pages",
                mechanism="A page that does not point to a related next step drops both users and crawlers.",
                impact="Sessions end; related products or docs are never reached.",
                observation=(
                    f"{len(signals.dead_end_urls)} product/service/article/docs page(s) expose ≤1 internal link."
                ),
                source_urls=signals.dead_end_urls[:8],
                metrics={"dead_end_urls": signals.dead_end_urls[:12]},
                action_summary="Add contextual links to related products, pricing, docs, or contact on those templates.",
                confidence=0.8,
                scope_pages=len(signals.dead_end_urls),
                scope_fraction=len(signals.dead_end_urls) / n,
                impact_weight=2,
            )
        )

    if signals.broken_internal:
        findings.append(
            make_finding(
                id="EG-005",
                category="engagement",
                title="Visitors are sent to broken internal URLs",
                mechanism_code="broken_internal_links",
                mechanism="A 404 mid-journey is a hard stop for a new visitor.",
                impact="Trust and continuation collapse on that path.",
                observation=f"{len(signals.broken_internal)} crawled internal URL(s) returned 404/410.",
                source_urls=signals.broken_internal[:8],
                metrics={"broken_urls": signals.broken_internal[:12]},
                action_summary="Redirect or rewrite the broken hrefs to live pages.",
                confidence=0.9,
                scope_pages=len(signals.broken_internal),
                scope_fraction=len(signals.broken_internal) / n,
                impact_weight=2,
            )
        )

    if signals.missing_next_step:
        findings.append(
            make_finding(
                id="EG-006",
                category="engagement",
                title="Homepage does not connect to an observed next-step path",
                mechanism_code="missing_continuation",
                mechanism="If pricing, products, or contact exist but the homepage does not link to them, visitors cannot continue naturally.",
                impact="The site answers 'what is this?' poorly and hides the conversion path.",
                observation="; ".join(signals.missing_next_step),
                source_urls=[homepage.url] if homepage else [],
                metrics={"gaps": signals.missing_next_step, "site_type": snapshot.site_type},
                action_summary="Link the homepage primary CTA to the real pricing, product, or contact URL that already exists.",
                confidence=0.77,
                scope_pages=1,
                scope_fraction=0.4,
                impact_weight=2,
            )
        )

    if signals.mobile_issues:
        findings.append(
            make_finding(
                id="EG-007",
                category="mobile",
                title="Mobile viewport shows measurable engagement blockers",
                mechanism_code="mobile_engagement_blocker",
                mechanism="Horizontal overflow, missing nav, or a vanished CTA stops mobile visitors.",
                impact="A large share of first visits cannot complete the next action.",
                observation=f"{len(signals.mobile_issues)} rendered mobile page(s) had measurable issues.",
                source_urls=[item.partition(": ")[0] for item in signals.mobile_issues],
                metrics={"issues": signals.mobile_issues},
                action_summary="Fix overflow and keep the primary nav/CTA available at a 390×844 viewport.",
                confidence=0.8,
                scope_pages=len(signals.mobile_issues),
                scope_fraction=len(signals.mobile_issues) / max(len({r.url for r in snapshot.rendered}), 1),
                impact_weight=2,
            )
        )

    deep_pages = [page for page in pages if page.role in {"article", "docs", "product"} and page.url.count("/") >= 3]
    if deep_pages and homepage:
        without_context = []
        for page in deep_pages:
            html = (page.html or "").lower()
            text = page.text or ""
            has_crumb = "breadcrumb" in html
            mentions_brand = False
            if snapshot.entities:
                brand = snapshot.entities[0].name.lower()
                mentions_brand = brand in text.lower() or brand in (page.title or "").lower()
            if not has_crumb and not mentions_brand and "home" not in html:
                without_context.append(page.url)
        if len(without_context) >= 2:
            findings.append(
                make_finding(
                    id="EG-008",
                    category="engagement",
                    title="Deep pages do not retain site context",
                    mechanism_code="weak_context_retention",
                    mechanism="Landing on a deep URL without brand, crumb, or home path leaves the visitor unoriented.",
                    impact="Assistants quoting that page may omit the parent organization; users cannot navigate up.",
                    observation=(
                        f"{len(without_context)} deep page(s) lack breadcrumbs, a brand mention, and a home path."
                    ),
                    source_urls=without_context[:8],
                    metrics={"pages": without_context[:8]},
                    action_summary="Add breadcrumbs plus the organization name in the header of deep templates.",
                    confidence=0.72,
                    scope_pages=len(without_context),
                    scope_fraction=len(without_context) / n,
                    impact_weight=2,
                )
            )

    return findings

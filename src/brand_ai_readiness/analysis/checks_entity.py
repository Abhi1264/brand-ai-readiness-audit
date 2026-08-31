from __future__ import annotations

from brand_ai_readiness.analysis.entities import is_under_specified, naming_variants, organization_names
from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.analysis.freshness import page_freshness
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.snapshot import CrawlSnapshot


def entity_findings(snapshot: CrawlSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    pages = snapshot.successful_pages()
    n = max(len(pages), 1)

    variants = naming_variants(snapshot)
    if len(variants) >= 2:
        findings.append(
            make_finding(
                id="FE-001",
                category="entity",
                title="The site uses inconsistent organization / brand names",
                mechanism_code="inconsistent_entity_name",
                mechanism="Machines merge entities by string similarity; conflicting official names create split identities.",
                impact="The brand may be cited under the wrong name or treated as two organizations.",
                observation=f"Observed distinct organization/brand strings: {variants}.",
                source_urls=[entity.sources[0] for entity in snapshot.entities if entity.name in variants][:6],
                metrics={"variants": variants, "entity_count": len(snapshot.entities)},
                quotes=variants[:4],
                action_summary="Pick one official name and use it in the title, visible copy, and Organization JSON-LD.",
                confidence=0.8,
                scope_pages=len(variants),
                scope_fraction=0.6,
                impact_weight=2,
            )
        )

    if is_under_specified(snapshot):
        names = organization_names(snapshot)
        findings.append(
            make_finding(
                id="FE-002",
                category="entity",
                title="The primary brand name is under-specified on the site itself",
                mechanism_code="entity_ambiguity",
                mechanism=(
                    "Short generic names collide with unrelated organizations. Sites need industry, place, "
                    "legal form, or sameAs links so a machine can disambiguate."
                ),
                impact="Assistants may attribute facts from a different entity that shares the name.",
                observation=(
                    f"Primary observed name(s) {names or ['(title fragment)']} lack a combination of "
                    "industry + location + legal suffix + sameAs on the crawled pages."
                ),
                source_urls=[page.url for page in pages[:4]],
                metrics={"names": names, "sameAs_present": any(e.same_as for e in snapshot.entities)},
                action_summary="Add a one-sentence disambiguator (what + where) and sameAs links to official profiles.",
                action_details="Do not invent a knowledge-graph ID. Use the organization's own website, LinkedIn, Wikipedia, or Wikidata if they exist.",
                confidence=0.7,
                scope_pages=1,
                scope_fraction=0.5,
                impact_weight=2,
            )
        )

    if pages and not snapshot.entities:
        findings.append(
            make_finding(
                id="FE-003",
                category="entity",
                title="No stable organization or product entity could be extracted",
                mechanism_code="missing_entity",
                mechanism="If a crawler cannot name the organization, it cannot attach later facts to that brand.",
                impact="The site is harder to retrieve as an answer about a specific company.",
                observation=(
                    f"No organization/brand/product name was extracted from titles, Open Graph, or JSON-LD "
                    f"across {n} crawled page(s)."
                ),
                source_urls=[page.url for page in pages[:5]],
                metrics={"pages_checked": n},
                action_summary="Put the organization name in the homepage title, H1 or first paragraph, and Organization JSON-LD.",
                confidence=0.75,
                scope_pages=n,
                scope_fraction=0.7,
                impact_weight=3,
            )
        )

    stale = []
    undated_sensitive = []
    for page in pages:
        if page.role not in {"homepage", "about", "product", "pricing", "article"}:
            continue
        dates = {}
        for block in snapshot.structured:
            if block.url == page.url and block.kind == "jsonld":
                for key in ("datePublished", "dateModified"):
                    if key in block.data and isinstance(block.data[key], str):
                        dates[key] = block.data[key]
        signal = page_freshness(page, dates)
        if signal.status == "stale_time_sensitive":
            stale.append(signal)
        if signal.status == "freshness_cannot_be_established" and signal.time_sensitive and page.role in {"pricing", "article"}:
            undated_sensitive.append(signal)

    if stale:
        findings.append(
            make_finding(
                id="FE-004",
                category="freshness",
                title="Time-sensitive pages have explicit modification dates older than two years",
                mechanism_code="stale_time_sensitive",
                mechanism="Assistants discount or hedge facts that look old when the topic is time-sensitive.",
                impact="Pricing or 'current' claims may be treated as unreliable.",
                observation=(
                    f"{len(stale)} page(s) combine time-sensitive language with a parsed date older than two years."
                ),
                source_urls=[item.url for item in stale],
                metrics={
                    "examples": [
                        {
                            "url": item.url,
                            "date_modified": item.date_modified,
                            "visible_date": item.visible_date,
                            "copyright_year": item.copyright_year,
                        }
                        for item in stale[:6]
                    ]
                },
                notes=["Copyright year alone was not used as a modification date."],
                action_summary="Update the content or the visible/structured dateModified so they match reality.",
                confidence=0.86,
                scope_pages=len(stale),
                scope_fraction=max(len(stale) / n, 0.45),
                impact_weight=3,
            )
        )

    if undated_sensitive:
        findings.append(
            make_finding(
                id="FE-005",
                category="freshness",
                title="Time-sensitive pages have no usable freshness signal",
                mechanism_code="freshness_unknown",
                mechanism="When pricing or news copy has no datePublished/dateModified, machines cannot tell if it is current.",
                impact="The safer assistant behavior is to ignore or hedge the claim.",
                observation=(
                    f"{len(undated_sensitive)} pricing/article page(s) use time-sensitive language, but freshness "
                    "cannot be established from structured or visible dates."
                ),
                source_urls=[item.url for item in undated_sensitive],
                metrics={"pages": [item.url for item in undated_sensitive]},
                notes=["Absence of a date is not treated as proof the content is stale."],
                action_summary="Add a visible last-updated date and dateModified on time-sensitive templates.",
                confidence=0.7,
                scope_pages=len(undated_sensitive),
                scope_fraction=len(undated_sensitive) / n,
                impact_weight=1,
            )
        )

    return findings

from __future__ import annotations

from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.analysis.site_type import expected_schema_types
from brand_ai_readiness.analysis.structured import (
    jsonld_types_on,
    malformed_jsonld_pages,
    name_mismatches,
    price_mismatches,
)
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.snapshot import CrawlSnapshot


def structured_findings(snapshot: CrawlSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    pages = snapshot.successful_pages()
    n = max(len(pages), 1)
    checked_urls = [page.url for page in pages]
    types = jsonld_types_on(snapshot)
    jsonld_pages = {block.url for block in snapshot.structured if block.kind == "jsonld" and not block.parse_error}
    malformed = list(dict.fromkeys(malformed_jsonld_pages(snapshot)))

    if malformed:
        findings.append(
            make_finding(
                id="SD-001",
                category="structured_data",
                title="Malformed JSON-LD was observed on crawled pages",
                mechanism_code="malformed_jsonld",
                mechanism="Invalid JSON-LD is ignored by consumers that parse structured data.",
                impact="Declared entities never enter the machine-readable graph.",
                observation=f"{len(malformed)} page(s) contain a script type=application/ld+json that did not parse as JSON.",
                source_urls=malformed[:8],
                metrics={"pages_with_malformed_jsonld": malformed[:8], "pages_checked": n},
                action_summary="Fix JSON-LD syntax (quotes, trailing commas, unescaped newlines) and validate the objects.",
                confidence=0.94,
                scope_pages=len(malformed),
                scope_fraction=len(malformed) / n,
                impact_weight=2,
            )
        )

    if pages and not jsonld_pages:
        findings.append(
            make_finding(
                id="SD-002",
                category="structured_data",
                title="No JSON-LD structured data was observed on crawled pages",
                mechanism_code="missing_jsonld",
                mechanism="Without explicit schema.org objects, machines must guess entities from prose.",
                impact="The site is harder to cite as a typed Organization, Product, or Article.",
                observation=(
                    f"No parseable JSON-LD was observed on {n} crawled HTML page(s). "
                    "This is a coverage statement about the crawled set, not a claim about unfetched URLs."
                ),
                source_urls=checked_urls[:8],
                metrics={"pages_checked": n, "jsonld_pages": 0, "site_type": snapshot.site_type},
                action_summary=(
                    f"Add JSON-LD that matches this site's apparent type ({snapshot.site_type}), "
                    f"starting with {', '.join(expected_schema_types(snapshot.site_type)[:3])}."
                ),
                action_details="Infer type from the site's own content. Do not add Product schema to a campus site.",
                confidence=0.86,
                scope_pages=n,
                scope_fraction=1.0,
                impact_weight=3,
            )
        )
    else:
        expected = expected_schema_types(snapshot.site_type)
        missing_expected = [item for item in expected if item not in types and item not in {"BreadcrumbList"}]
        # Only require Organization when we actually saw an organization-like homepage.
        homepage = snapshot.homepage()
        org_needed = homepage is not None and homepage.word_count >= 20
        if "Organization" in missing_expected and org_needed and snapshot.site_type != "unknown":
            findings.append(
                make_finding(
                    id="SD-003",
                    category="structured_data",
                    title="No Organization (or equivalent) JSON-LD was observed",
                    mechanism_code="missing_organization",
                    mechanism="Assistants use Organization markup to bind a brand name to a canonical URL.",
                    impact="The brand is easier to confuse with similarly named entities.",
                    observation=(
                        f"Crawled {n} page(s). Observed JSON-LD types: "
                        f"{sorted(types) or 'none'}. Organization was not among them."
                    ),
                    source_urls=[homepage.url] if homepage else checked_urls[:3],
                    metrics={"observed_types": sorted(types), "pages_checked": n, "site_type": snapshot.site_type},
                    action_summary="Add Organization JSON-LD on the homepage with a stable name, url, and sameAs profiles.",
                    confidence=0.8,
                    scope_pages=1,
                    scope_fraction=0.4,
                    impact_weight=2,
                )
            )

        product_pages = snapshot.pages_by_role("product")
        if product_pages and snapshot.site_type in {"ecommerce", "mixed"}:
            with_product = [page for page in product_pages if "Product" in jsonld_types_on(snapshot, page.url)]
            missing = [page.url for page in product_pages if page.url not in {p.url for p in with_product}]
            if missing:
                findings.append(
                    make_finding(
                        id="SD-004",
                        category="structured_data",
                        title="Product pages are missing Product/Offer JSON-LD",
                        mechanism_code="missing_product_schema",
                        mechanism="Product entities are much easier to extract when typed as schema.org Product + Offer.",
                        impact="Prices and product names are more likely to be omitted or mis-attributed.",
                        observation=(
                            f"{len(missing)} of {len(product_pages)} crawled product page(s) have no Product JSON-LD."
                        ),
                        source_urls=missing[:8],
                        metrics={
                            "product_pages_checked": len(product_pages),
                            "with_product_jsonld": len(with_product),
                            "missing": missing[:8],
                        },
                        action_summary="Add Product/Offer JSON-LD to every product template, matching visible name and price.",
                        confidence=0.88,
                        scope_pages=len(missing),
                        scope_fraction=len(missing) / max(len(product_pages), 1),
                        impact_weight=3,
                    )
                )

        article_pages = snapshot.pages_by_role("article")
        if article_pages and snapshot.site_type in {"article", "mixed"}:
            with_article = [page for page in article_pages if any(t in jsonld_types_on(snapshot, page.url) for t in ("Article", "NewsArticle", "BlogPosting"))]
            if len(with_article) == 0:
                findings.append(
                    make_finding(
                        id="SD-005",
                        category="structured_data",
                        title="Article pages have no Article JSON-LD",
                        mechanism_code="missing_article_schema",
                        mechanism="Article markup exposes headline, datePublished, and author as first-class fields.",
                        impact="Stories are harder to attribute and date-stamp in assistant answers.",
                        observation=f"0/{len(article_pages)} crawled article page(s) contained Article/NewsArticle/BlogPosting JSON-LD.",
                        source_urls=[page.url for page in article_pages[:6]],
                        metrics={"article_pages_checked": len(article_pages)},
                        action_summary="Add Article JSON-LD with headline, datePublished, and author on story templates.",
                        confidence=0.84,
                        scope_pages=len(article_pages),
                        scope_fraction=1.0,
                        impact_weight=2,
                    )
                )

        local_needed = snapshot.site_type == "local_business"
        if local_needed and not any(t in types for t in ("LocalBusiness", "Restaurant", "Store", "ProfessionalService")):
            findings.append(
                make_finding(
                    id="SD-006",
                    category="structured_data",
                    title="Local-business signals are present but LocalBusiness JSON-LD was not observed",
                    mechanism_code="missing_localbusiness",
                    mechanism="Local entities need address/geo typed data to avoid being treated as a generic website.",
                    impact="Location-bound questions are less likely to cite the business.",
                    observation=(
                        f"Site type inferred as local_business from {snapshot.site_type_signals}. "
                        f"Observed JSON-LD types: {sorted(types) or 'none'}."
                    ),
                    source_urls=checked_urls[:4],
                    metrics={"observed_types": sorted(types)},
                    action_summary="Add LocalBusiness JSON-LD with name, address, and url on the homepage.",
                    confidence=0.78,
                    scope_pages=1,
                    scope_fraction=0.5,
                    impact_weight=2,
                )
            )

    mismatch_pages = []
    for page in pages:
        names = name_mismatches(page, snapshot)
        prices = price_mismatches(page, snapshot)
        if names or prices:
            mismatch_pages.append({"url": page.url, "names": names, "prices": prices})
    if mismatch_pages:
        findings.append(
            make_finding(
                id="SD-007",
                category="structured_data",
                title="Structured data does not match visible page content",
                mechanism_code="structured_visible_mismatch",
                mechanism="Consumers prefer explicit markup but will distrust it when it contradicts visible text.",
                impact="The wrong product name or price may be quoted.",
                observation=(
                    f"{len(mismatch_pages)} page(s) have JSON-LD/OG names or prices that were not found in visible text."
                ),
                source_urls=[item["url"] for item in mismatch_pages[:8]],
                metrics={"examples": mismatch_pages[:5]},
                action_summary="Align JSON-LD name/price/url fields with the visible HTML for those templates.",
                confidence=0.74,
                scope_pages=len(mismatch_pages),
                scope_fraction=len(mismatch_pages) / n,
                impact_weight=2,
            )
        )

    og_pages = {block.url for block in snapshot.structured if block.kind == "opengraph"}
    if pages and not og_pages and not jsonld_pages:
        findings.append(
            make_finding(
                id="SD-008",
                category="structured_data",
                title="No Open Graph title/description metadata was observed",
                mechanism_code="missing_opengraph",
                mechanism="og:title and og:description are a widely consumed fallback when JSON-LD is absent.",
                impact="Link unfurls and some crawlers get a weaker title/description pair.",
                observation=f"0/{n} crawled page(s) exposed og:* meta tags.",
                source_urls=checked_urls[:5],
                metrics={"pages_checked": n},
                action_summary="Add og:title, og:description, and og:url on the homepage and key templates.",
                confidence=0.72,
                scope_pages=n,
                scope_fraction=0.5,
                impact_weight=1,
            )
        )

    return findings

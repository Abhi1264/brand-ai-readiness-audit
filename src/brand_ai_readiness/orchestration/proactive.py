"""Contextual proactive recommendations — only when they fit the site."""

from __future__ import annotations

from brand_ai_readiness.analysis.site_type import expected_schema_types
from brand_ai_readiness.analysis.structured import jsonld_types_on
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.report import ProactiveRecommendation
from brand_ai_readiness.models.snapshot import CrawlSnapshot


def proactive_recommendations(snapshot: CrawlSnapshot, findings: list[Finding]) -> list[ProactiveRecommendation]:
    codes = {item.mechanism_code for item in findings}
    recs: list[ProactiveRecommendation] = []
    types = jsonld_types_on(snapshot)
    homepage = snapshot.homepage()

    if "Organization" in types and "sameAs" not in {
        key for block in snapshot.structured for key in block.data
    }:
        recs.append(
            ProactiveRecommendation(
                summary="Attach official sameAs profile URLs to the existing Organization entity",
                why_it_matters=(
                    f"This {snapshot.site_type} site already exposes Organization markup; linking official "
                    "profiles gives assistants a way to bind the brand to independent identifiers."
                ),
                what_to_change="Add sameAs to LinkedIn, Wikipedia/Wikidata, or the official social profiles the org actually uses.",
                expected_benefit="Lower chance of mixing this brand with a similarly named organization.",
                priority="medium",
            )
        )

    if snapshot.site_type in {"ecommerce", "saas"} and "missing_product_schema" not in codes:
        expected = expected_schema_types(snapshot.site_type)
        if "Offer" not in types and "Product" in types:
            recs.append(
                ProactiveRecommendation(
                    summary="Add Offer objects next to existing Product JSON-LD",
                    why_it_matters="Product pages already have typed names; price/availability still have to be inferred from prose.",
                    what_to_change="Include offers.price, priceCurrency, and url on each product template.",
                    expected_benefit="Assistants can quote a price without guessing from nearby text.",
                    priority="medium",
                )
            )
        elif "Product" not in types and any(page.role == "product" for page in snapshot.pages):
            recs.append(
                ProactiveRecommendation(
                    summary=f"Introduce {expected[2] if len(expected) > 2 else 'Product'} markup on the product template",
                    why_it_matters="The crawl already found product-like URLs; typed offers would make them citable.",
                    what_to_change="Add Product JSON-LD that repeats the visible name and price.",
                    expected_benefit="Higher chance of being selected as a source for product questions.",
                    priority="high",
                )
            )

    if homepage and homepage.word_count >= 40 and "weak_homepage_orientation" not in codes:
        recs.append(
            ProactiveRecommendation(
                summary="Add a 2–3 sentence factual summary block that a machine can quote verbatim",
                why_it_matters=(
                    "The homepage already has enough prose to orient a human; a compact fact box "
                    "(what you do, who for, where) is what assistants copy."
                ),
                what_to_change="Place an unambiguous summary near the H1: name, offering, audience, primary location if relevant.",
                expected_benefit="More accurate one-line citations and fewer invented descriptions.",
                priority="medium",
            )
        )

    if snapshot.pages_by_role("article") and "freshness_unknown" not in codes:
        recs.append(
            ProactiveRecommendation(
                summary="Surface dateModified on article templates even when content is recent",
                why_it_matters="Dated articles are easier to trust in retrieval than undated posts of unknown age.",
                what_to_change="Show a visible updated date and emit dateModified in Article JSON-LD.",
                expected_benefit="Time-sensitive answers can cite the story with an explicit timestamp.",
                priority="low",
            )
        )

    deep = [page for page in snapshot.successful_pages() if page.role in {"docs", "article", "product"}]
    if deep and "weak_context_retention" not in codes:
        recs.append(
            ProactiveRecommendation(
                summary="Keep a persistent parent-context link on deep pages",
                why_it_matters=f"{len(deep)} deep page(s) were crawled; visitors who land there still need a path back to the org and a next action.",
                what_to_change="Add breadcrumbs plus a contextual CTA (docs→pricing, product→contact) on those templates.",
                expected_benefit="Better continuation and clearer attribution when a deep URL is the cited source.",
                priority="medium",
            )
        )

    if snapshot.stats.rendering_status in {"unavailable", "skipped"}:
        recs.append(
            ProactiveRecommendation(
                summary="Keep commercially important strings in the initial HTML even if the UI is a JS app",
                why_it_matters="This audit could not fully rely on a browser; many assistants are in the same position.",
                what_to_change="Prerender title, primary description, and prices, or duplicate them in JSON-LD.",
                expected_benefit="Discoverability no longer depends on a headless browser.",
                priority="medium",
            )
        )

    # Cap so the report stays prioritized, not a dump.
    return recs[:6]

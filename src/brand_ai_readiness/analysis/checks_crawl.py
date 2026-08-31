from __future__ import annotations

from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.analysis.machine_readability import image_only_fact_pages
from brand_ai_readiness.crawler.urls import normalize_url
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.snapshot import CrawlSnapshot
from brand_ai_readiness.rendering.compare import compare_raw_and_rendered


def crawl_findings(snapshot: CrawlSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    pages = snapshot.pages
    success = snapshot.successful_pages()
    n = max(len(pages), 1)

    blocked = [page for page in pages if page.robots_blocked]
    important_blocked = [page for page in blocked if page.role in {"homepage", "about", "product", "pricing", "contact"}]
    if important_blocked:
        findings.append(
            make_finding(
                id="CR-001",
                category="crawlability",
                title="robots.txt blocks important pages that the audit needed to read",
                mechanism_code="robots_blocks_important",
                mechanism="Disallow rules prevent a simple crawler from fetching important URLs.",
                impact="AI assistants and search crawlers that honor robots.txt will not see those pages.",
                observation=(
                    f"{len(blocked)} of {len(pages)} fetched-or-attempted URLs were disallowed by robots.txt, "
                    f"including {len(important_blocked)} important page(s)."
                ),
                source_urls=[page.url for page in important_blocked],
                metrics={
                    "pages_checked": len(pages),
                    "blocked_pages": len(blocked),
                    "blocked_urls": [page.url for page in blocked[:12]],
                },
                action_summary="Allow crawlers to fetch public marketing, product, and about URLs in robots.txt.",
                action_details=(
                    "Keep Disallow for private/admin paths. Remove or narrow rules that hide public product, "
                    "about, pricing, or homepage-equivalent URLs."
                ),
                rationale="Only audited URLs that were actually disallowed are flagged.",
                implementation_direction="Edit robots.txt User-agent: * Disallow rules; re-check with a robots tester.",
                confidence=0.95,
                scope_pages=len(blocked),
                scope_fraction=len(blocked) / n,
                impact_weight=4 if any(page.role == "homepage" for page in important_blocked) else 3,
            )
        )

    failed_http = [
        page
        for page in pages
        if page.status_code and page.status_code >= 400 and not page.robots_blocked
    ]
    important_failed = [page for page in failed_http if page.role in {"homepage", "about", "product", "pricing"}]
    if important_failed:
        findings.append(
            make_finding(
                id="CR-002",
                category="crawlability",
                title="Important pages return non-2xx HTTP status",
                mechanism_code="important_http_error",
                mechanism="Crawlers drop or distrust URLs that do not return a successful status.",
                impact="Those URLs cannot be reliably indexed or cited.",
                observation=(
                    f"{len(important_failed)} important page(s) returned non-2xx status among {len(pages)} attempts."
                ),
                source_urls=[page.url for page in important_failed],
                metrics={
                    "status_codes": {page.url: page.status_code for page in important_failed[:10]},
                },
                action_summary="Restore 2xx responses for public important URLs or 301 them to live replacements.",
                confidence=0.93,
                scope_pages=len(important_failed),
                scope_fraction=len(important_failed) / n,
                impact_weight=4 if any(page.role == "homepage" for page in important_failed) else 3,
            )
        )

    loops = [page for page in pages if page.error in {"redirect_loop", "excessive_redirects"}]
    if loops:
        findings.append(
            make_finding(
                id="CR-003",
                category="crawlability",
                title="Redirect loops or excessive redirects on crawled URLs",
                mechanism_code="redirect_failure",
                mechanism="Crawlers abandon URLs that bounce too many times.",
                impact="Affected pages are treated as unreachable.",
                observation=f"{len(loops)} URL(s) exhausted the redirect budget or looped.",
                source_urls=[page.url for page in loops],
                metrics={"errors": {page.url: page.error for page in loops}},
                action_summary="Collapse redirect chains to a single 301 toward the canonical URL.",
                confidence=0.9,
                scope_pages=len(loops),
                scope_fraction=len(loops) / n,
                impact_weight=3,
            )
        )

    mismatches = []
    for page in success:
        if page.canonical and page.final_url:
            left = normalize_url(page.canonical) or page.canonical
            right = normalize_url(page.final_url) or page.final_url
            if left and right and left != right:
                mismatches.append((page.url, page.canonical))
    if len(mismatches) >= 2 or (
        mismatches and any(page.role == "homepage" for page in success if page.url == mismatches[0][0])
    ):
        findings.append(
            make_finding(
                id="CR-004",
                category="crawlability",
                title="Canonical URLs disagree with the fetched URL on multiple pages",
                mechanism_code="canonical_inconsistency",
                mechanism="Conflicting canonicals split crawl signals across URL variants.",
                impact="Assistants may fetch a variant that is not the one the site declares canonical.",
                observation=f"{len(mismatches)} page(s) declare a canonical that is not the fetched URL.",
                source_urls=[item[0] for item in mismatches[:8]],
                metrics={"examples": [{"url": u, "canonical": c} for u, c in mismatches[:6]]},
                action_summary="Make each public page self-canonical, or consistently point to one live variant.",
                confidence=0.78,
                scope_pages=len(mismatches),
                scope_fraction=len(mismatches) / max(len(success), 1),
                impact_weight=2,
            )
        )

    noindex_important = [page for page in success if page.noindex and page.role in {"homepage", "product", "about"}]
    if noindex_important:
        findings.append(
            make_finding(
                id="CR-005",
                category="crawlability",
                title="Important pages carry a noindex robots directive",
                mechanism_code="noindex_important",
                mechanism="noindex tells crawlers not to keep the page in an index.",
                impact="The page can be fetched but is unlikely to be cited as a source.",
                observation=f"{len(noindex_important)} important page(s) include a noindex robots meta tag.",
                source_urls=[page.url for page in noindex_important],
                metrics={"robots_meta": {page.url: page.robots_meta for page in noindex_important}},
                action_summary="Remove noindex from public pages that should be discoverable.",
                confidence=0.92,
                scope_pages=len(noindex_important),
                scope_fraction=len(noindex_important) / max(len(success), 1),
                impact_weight=3,
            )
        )

    if snapshot.robots.sitemaps and not snapshot.sitemap.urls and snapshot.sitemap.errors:
        findings.append(
            make_finding(
                id="CR-006",
                category="crawlability",
                title="Declared sitemap could not be used",
                mechanism_code="sitemap_inaccessible",
                mechanism="A sitemap listed in robots.txt did not yield same-origin URLs.",
                impact="Crawlers miss URLs that are not linked from the homepage.",
                observation="robots.txt lists sitemap URL(s), but no usable same-origin loc entries were parsed.",
                source_urls=snapshot.robots.sitemaps[:4],
                metrics={"errors": snapshot.sitemap.errors[:6], "discovered": snapshot.sitemap.discovered},
                action_summary="Publish a reachable sitemap.xml with absolute same-origin <loc> entries.",
                confidence=0.8,
                scope_pages=0,
                scope_fraction=0.3,
                impact_weight=2,
            )
        )

    type_mismatch = [
        page
        for page in pages
        if page.fetch_status == "partial" and page.error == "non_html" and page.role in {"homepage", "about", "product"}
    ]
    if type_mismatch:
        findings.append(
            make_finding(
                id="CR-007",
                category="crawlability",
                title="Important URLs did not return HTML",
                mechanism_code="content_type_mismatch",
                mechanism="A non-HTML response cannot be parsed for facts by a simple reader.",
                impact="The URL is effectively unreadable to text-oriented crawlers.",
                observation=f"{len(type_mismatch)} important URL(s) returned a non-HTML content type.",
                source_urls=[page.url for page in type_mismatch],
                metrics={"content_types": {page.url: page.content_type for page in type_mismatch}},
                action_summary="Serve text/html for document URLs, and keep binary assets on distinct paths.",
                confidence=0.88,
                scope_pages=len(type_mismatch),
                scope_fraction=len(type_mismatch) / n,
                impact_weight=3,
            )
        )

    gaps = []
    for page in success:
        rendered = snapshot.desktop_rendered(page)
        if not rendered:
            continue
        gap = compare_raw_and_rendered(page, rendered)
        if gap.meaningful:
            gaps.append(gap)
    if gaps:
        findings.append(
            make_finding(
                id="CR-008",
                category="rendering",
                title="Important information is missing from raw HTML and appears only after rendering",
                mechanism_code="js_content_gap",
                mechanism=(
                    "Many assistants fetch raw HTML without executing JavaScript. Facts that exist only "
                    "after render are invisible to those readers."
                ),
                impact="The brand can look empty or incomplete in AI answers even though a browser shows content.",
                observation=(
                    f"{len(gaps)} of {max(len([p for p in success if snapshot.desktop_rendered(p)]), 1)} "
                    f"rendered page(s) expose meaningful facts only after JavaScript execution."
                ),
                source_urls=[gap.url for gap in gaps],
                metrics={
                    "examples": [
                        {
                            "url": gap.url,
                            "raw_words": gap.raw_words,
                            "rendered_words": gap.rendered_words,
                            "facts_only_in_render": gap.facts_only_in_render,
                        }
                        for gap in gaps[:6]
                    ]
                },
                action_summary="Server-render or prerender titles, prices, and primary descriptions in HTML.",
                action_details=(
                    "Keep the JavaScript app. Also include the commercially important strings in the initial HTML "
                    "or in JSON-LD so a non-JS reader can extract them."
                ),
                rationale="JavaScript itself is not the defect; missing pre-render facts are.",
                implementation_direction="SSR/SSG the homepage and product templates; add JSON-LD as a fallback.",
                confidence=0.9,
                scope_pages=len(gaps),
                scope_fraction=len(gaps) / max(len(success), 1),
                impact_weight=3,
            )
        )

    image_facts = image_only_fact_pages(success)
    if image_facts:
        findings.append(
            make_finding(
                id="CR-009",
                category="machine_readability",
                title="Important facts appear to exist only in images or canvas, not readable HTML text",
                mechanism_code="image_only_facts",
                mechanism="Simple readers extract text nodes, not pixels inside images or canvas.",
                impact="Prices, names, or claims locked in images are skipped or misquoted.",
                observation=(
                    f"{len(image_facts)} page(s) show fact-like content in image alt text or canvas "
                    "without equivalent visible HTML text."
                ),
                source_urls=[str(item["url"]) for item in image_facts],
                metrics={"pages": image_facts[:6]},
                action_summary="Repeat prices, names, and key claims as real HTML text (and optionally in JSON-LD).",
                confidence=0.82,
                scope_pages=len(image_facts),
                scope_fraction=len(image_facts) / max(len(success), 1),
                impact_weight=3,
            )
        )

    if snapshot.sitemap.urls:
        linked: set[str] = set()
        for page in success:
            linked.update(page.internal_links)
            linked.add(page.url)
        orphans = [url for url in snapshot.sitemap.urls if url not in linked][:20]
        important_orphans = [
            url
            for url in orphans
            if any(token in url.lower() for token in ("/product", "/about", "/pricing", "/contact"))
        ]
        if len(important_orphans) >= 2:
            findings.append(
                make_finding(
                    id="CR-010",
                    category="crawlability",
                    title="Sitemap lists important URLs that were not linked from crawled pages",
                    mechanism_code="orphaned_important",
                    mechanism="Pages that are not in the internal link graph are harder for crawlers to rediscover.",
                    impact="Coverage depends entirely on the sitemap remaining accurate.",
                    observation=(
                        f"{len(important_orphans)} sitemap URL(s) look important and were not observed "
                        f"in internal links from {len(success)} crawled page(s)."
                    ),
                    source_urls=important_orphans[:8],
                    metrics={"pages_crawled": len(success), "orphan_examples": important_orphans[:8]},
                    action_summary="Add contextual internal links to those URLs from the homepage or section hubs.",
                    confidence=0.7,
                    scope_pages=len(important_orphans),
                    scope_fraction=min(1.0, len(important_orphans) / max(len(snapshot.sitemap.urls), 1)),
                    impact_weight=2,
                )
            )

    targets = {page.url: page for page in pages}
    linked_404 = list(
        dict.fromkeys(
            link
            for page in success
            for link in page.internal_links
            if (target := targets.get(link)) and target.status_code in {404, 410}
        )
    )
    if linked_404:
        findings.append(
            make_finding(
                id="CR-011",
                category="crawlability",
                title="Broken internal links were observed during the crawl",
                mechanism_code="broken_internal_links",
                mechanism="Dead internal links waste crawl budget and strand visitors.",
                impact="Both humans and machines fail to reach the promised page.",
                observation=f"{len(linked_404)} internal URL(s) linked from crawled pages returned 404/410.",
                source_urls=linked_404[:8],
                metrics={"broken_urls": linked_404[:12], "pages_checked": len(pages)},
                action_summary="Fix or redirect the broken internal targets and remove stale hrefs.",
                confidence=0.9,
                scope_pages=len(linked_404),
                scope_fraction=len(linked_404) / n,
                impact_weight=2,
            )
        )

    return findings

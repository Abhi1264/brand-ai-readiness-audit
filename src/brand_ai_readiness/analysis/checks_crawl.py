from __future__ import annotations

from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.analysis.machine_readability import image_only_fact_pages
from brand_ai_readiness.crawler.urls import normalize_url
from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.models.snapshot import CrawlSnapshot
from brand_ai_readiness.rendering.compare import compare_raw_and_rendered


def _access_probe_findings(snapshot: CrawlSnapshot, robots_already_flagged: bool) -> list[Finding]:
    """Compare declared robots policy against what the origin actually serves.

    Only a *status* divergence triggers a finding. Body-length differences alone
    are not evidence of bot policy — personalization, A/B tests, geo variants and
    cookie walls all move body size — so length is recorded as supporting metrics
    and never as the trigger.
    """
    if snapshot.access_probe_status != "complete":
        return []
    browser = snapshot.browser_probe()
    ai_probes = snapshot.ai_probes()
    # Without a browser baseline that succeeded there is nothing to compare
    # against: an origin that refuses everyone (paywall, geo-block, auth wall)
    # is not an AI-crawler policy problem.
    if browser is None or not browser.reachable() or not ai_probes:
        return []

    blocked = [probe for probe in ai_probes if probe.status_code >= 400]
    if not blocked:
        return []

    # A permissive robots verdict only means something when robots.txt was
    # actually readable. When it was not, allows_for() defaults to True for
    # crawling purposes -- but "we could not read robots.txt" is not the same
    # claim as "robots.txt permits this agent", and reporting it as the latter
    # invents a contradiction that was never observed.
    robots_known = snapshot.robots.available
    contradicted = [probe for probe in blocked if robots_known and probe.robots_allows]
    consistent = [probe for probe in blocked if robots_known and not probe.robots_allows]
    undetermined = [] if robots_known else list(blocked)
    # Flat scalars only: metrics are rendered into a prose evidence string, so a
    # nested dict would surface to the reader as a Python repr.
    metrics: dict[str, object] = {
        "probe_url": snapshot.start_url,
        "probe_method": browser.method,
        "browser_status": browser.status_code,
    }
    for probe in ai_probes:
        metrics[f"{probe.agent}_status"] = probe.status_code
        metrics[f"{probe.agent}_robots_allows"] = "yes" if probe.robots_allows else "no"

    findings: list[Finding] = []
    if contradicted:
        names = ", ".join(probe.agent for probe in contradicted)
        findings.append(
            make_finding(
                id="CR-010",
                category="crawlability",
                title="Server blocks AI crawlers that robots.txt permits",
                mechanism_code="ai_crawler_edge_blocked",
                mechanism=(
                    "robots.txt is a request a crawler honors; the CDN/WAF decides what is "
                    "actually served. Here the two disagree: robots.txt allows these agents "
                    "but the origin refuses them by user-agent."
                ),
                impact=(
                    "Assistants using these crawlers never receive the page, so the brand "
                    "cannot be cited from it — and robots.txt gives no indication anything "
                    "is wrong."
                ),
                observation=(
                    f"{snapshot.start_url} returned {browser.status_code} to a browser "
                    f"user-agent but {', '.join(f'{p.status_code} to {p.agent}' for p in contradicted)}. "
                    f"robots.txt permits {names}."
                ),
                source_urls=[snapshot.start_url],
                metrics=metrics,
                action_summary=(
                    f"Allow {names} through the CDN/WAF bot rules, or remove the user-agent "
                    "block, so the permission already stated in robots.txt is actually honored."
                ),
                action_details=(
                    "Check bot-management settings (Cloudflare 'Block AI Bots'/'AI Scrapers', "
                    "Akamai Bot Manager, or a server-level user-agent deny rule). Either allow "
                    "these agents or, if exclusion is intended, state it in robots.txt so the "
                    "policy is consistent and diagnosable."
                ),
                rationale=(
                    "Flagged only because a browser user-agent succeeded on the same URL in "
                    "the same run, and robots.txt does not disallow these agents."
                ),
                implementation_direction=(
                    "Edge/WAF bot rules, then re-probe the homepage with the agent's "
                    "user-agent string to confirm a 2xx."
                ),
                confidence=0.9,
                scope_pages=1,
                # Edge policy is origin-wide, not a property of the probed page.
                scope_fraction=1.0,
                impact_weight=4,
            )
        )

    # Consistent exclusion (robots says no and the server enforces it) is a
    # deliberate policy, not a defect. Report it once, and only when the robots
    # finding has not already covered the same ground.
    if consistent and not contradicted and not robots_already_flagged:
        names = ", ".join(probe.agent for probe in consistent)
        findings.append(
            make_finding(
                id="CR-011",
                category="crawlability",
                title="AI crawlers are excluded by both robots.txt and the server",
                mechanism_code="ai_crawler_excluded_by_policy",
                mechanism=(
                    "robots.txt disallows these agents and the origin also refuses them at "
                    "the edge. The exclusion is consistent and appears deliberate."
                ),
                impact=(
                    "These assistants cannot retrieve the page, so the brand will not be "
                    "cited from it regardless of how well the content is written."
                ),
                observation=(
                    f"{snapshot.start_url} returned {browser.status_code} to a browser "
                    f"user-agent and {', '.join(f'{p.status_code} to {p.agent}' for p in consistent)}. "
                    f"robots.txt also disallows {names}."
                ),
                source_urls=[snapshot.start_url],
                metrics=metrics,
                action_summary=(
                    f"Confirm that excluding {names} is intended; if it is not, remove the "
                    "Disallow rules and the matching edge block."
                ),
                action_details=(
                    "This is a business decision, not a bug. If the exclusion is deliberate "
                    "(licensing, paywall), no change is needed and low AI visibility is the "
                    "expected outcome. If it was inherited from a default bot-protection "
                    "setting, both robots.txt and the WAF rule must be changed together."
                ),
                rationale="Reported as a policy observation because both layers agree.",
                implementation_direction="robots.txt Disallow rules plus edge bot-management settings.",
                confidence=0.9,
                scope_pages=1,
                scope_fraction=1.0,
                impact_weight=2,
            )
        )

    # Blocked, but robots.txt could not be read: report the observation without
    # asserting whether the exclusion was intended.
    if undetermined:
        names = ", ".join(probe.agent for probe in undetermined)
        findings.append(
            make_finding(
                id="CR-012",
                category="crawlability",
                title="Server blocks AI crawlers (robots.txt could not be read)",
                mechanism_code="ai_crawler_blocked_robots_unknown",
                mechanism=(
                    "The origin refuses these agents by user-agent. robots.txt was not "
                    "retrievable during this audit, so the site's declared policy is unknown."
                ),
                impact=(
                    "These assistants cannot retrieve the page. Whether that is intended "
                    "could not be established from the evidence available."
                ),
                observation=(
                    f"{snapshot.start_url} returned {browser.status_code} to a browser "
                    f"user-agent but {', '.join(f'{p.status_code} to {p.agent}' for p in undetermined)}. "
                    "robots.txt was not readable, so its stated policy could not be compared."
                ),
                source_urls=[snapshot.start_url],
                metrics=metrics,
                action_summary=(
                    f"Publish a reachable robots.txt stating the intended policy for {names}, "
                    "then align the CDN/WAF bot rules with it."
                ),
                action_details=(
                    "Two things are unresolved: robots.txt did not return a usable response, "
                    "and the edge refuses these agents. Fix the former first so the intended "
                    "policy is stated, then confirm the edge rules match it."
                ),
                rationale=(
                    "Severity is held below critical because no contradiction was observed -- "
                    "only a block with no declared policy to compare against."
                ),
                implementation_direction="robots.txt availability, then edge bot-management rules.",
                confidence=0.75,
                scope_pages=1,
                scope_fraction=1.0,
                impact_weight=3,
            )
        )
    return findings


def crawl_findings(snapshot: CrawlSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    pages = snapshot.pages
    success = snapshot.successful_pages()
    n = max(len(pages), 1)

    robots_flagged = False
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
        robots_flagged = True

    findings.extend(_access_probe_findings(snapshot, robots_flagged))

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

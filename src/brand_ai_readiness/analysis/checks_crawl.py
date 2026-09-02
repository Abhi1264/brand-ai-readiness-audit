from __future__ import annotations

from brand_ai_readiness.analysis.finding_factory import make_finding
from brand_ai_readiness.analysis.machine_readability import image_only_fact_pages
from brand_ai_readiness.analysis.snippet_policy import (
    DATA_NOSNIPPET_DOMINANT,
    analyze_snippet_policy,
)
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
    # Only search-class crawlers decide whether a brand can be cited. Blocking
    # training-class bots (GPTBot, ClaudeBot, CCBot) while allowing the search
    # ones is a supported configuration, so it is recorded as context and never
    # raises a finding on its own.
    search_probes = snapshot.search_probes()
    training_probes = snapshot.training_probes()
    # Without a browser baseline that succeeded there is nothing to compare
    # against: an origin that refuses everyone (paywall, geo-block, auth wall)
    # is not an AI-crawler policy problem.
    if browser is None or not browser.reachable() or not search_probes:
        return []

    blocked = [probe for probe in search_probes if probe.status_code >= 400]
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
    for probe in search_probes:
        metrics[f"search_{probe.agent}_status"] = probe.status_code
        metrics[f"search_{probe.agent}_robots_allows"] = "yes" if probe.robots_allows else "no"
    # Training-class results are context for the reader, not part of the verdict.
    for probe in training_probes:
        metrics[f"training_{probe.agent}_status"] = probe.status_code

    findings: list[Finding] = []
    if contradicted:
        names = ", ".join(probe.agent for probe in contradicted)
        findings.append(
            make_finding(
                id="CR-010",
                category="crawlability",
                title="Server blocks AI search crawlers that robots.txt permits",
                mechanism_code="ai_crawler_edge_blocked",
                mechanism=(
                    "robots.txt is a request a crawler honors; the CDN/WAF decides what is "
                    "actually served. Here the two disagree: robots.txt allows these "
                    "search-class agents but the origin refuses them by user-agent. These "
                    "are the crawlers that decide whether the brand can be cited at all."
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
                title="AI search crawlers are excluded by both robots.txt and the server",
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
                title="Server blocks AI search crawlers (robots.txt could not be read)",
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


_CONTENT_ROLES = {"homepage", "about", "product", "service", "pricing", "article", "docs"}


def _snippet_findings(snapshot: CrawlSnapshot) -> list[Finding]:
    """Directives that suppress the snippet a page would otherwise be cited from.

    Restricted to content-bearing roles: nosnippet on a legal or account page is
    ordinary practice, not a discoverability problem.
    """
    pages = [page for page in snapshot.successful_pages() if page.role in _CONTENT_ROLES]
    if not pages:
        return []
    total = len(pages)
    policies = [
        analyze_snippet_policy(page.url, page.html, page.headers, page.robots_meta, page_text=page.text)
        for page in pages
    ]
    findings: list[Finding] = []

    nosnippet = [item for item in policies if item.nosnippet]
    if nosnippet:
        where = sorted({source for item in nosnippet for source in item.sources})
        findings.append(
            make_finding(
                id="CR-020",
                category="crawlability",
                title="nosnippet stops content being used by AI answer surfaces",
                mechanism_code="nosnippet_suppresses_ai",
                mechanism=(
                    "Google documents that nosnippet prevents the content from being used as "
                    "a direct input for AI Overviews and AI Mode, not merely from showing a "
                    "search snippet."
                ),
                impact=(
                    "The page can be crawled and indexed and still never be quoted, because "
                    "the text is withheld from the surface that would cite it."
                ),
                observation=(
                    f"{len(nosnippet)} of {total} content page(s) carry a nosnippet directive "
                    f"(via {', '.join(where) or 'robots directives'})."
                ),
                source_urls=[item.url for item in nosnippet[:8]],
                metrics={
                    "pages_checked": total,
                    "pages_with_nosnippet": len(nosnippet),
                    "directive_sources": ", ".join(where),
                },
                action_summary=(
                    "Remove nosnippet from pages that should be quotable, keeping it only "
                    "where content genuinely must not be excerpted."
                ),
                action_details=(
                    "Check both the robots meta tag and the X-Robots-Tag response header -- "
                    "either alone is enough to suppress the page, and a CDN or framework may "
                    "be adding the header without the markup showing it."
                ),
                rationale="Only pages that actually carry the directive are counted.",
                implementation_direction="robots meta tag and X-Robots-Tag response header.",
                confidence=0.95,
                scope_pages=len(nosnippet),
                scope_fraction=len(nosnippet) / total,
                impact_weight=3,
            )
        )

    limited = [item for item in policies if item.max_snippet_is_limiting and not item.nosnippet]
    if limited:
        findings.append(
            make_finding(
                id="CR-021",
                category="crawlability",
                title="max-snippet is set too low to carry a usable fact",
                mechanism_code="max_snippet_limits_ai",
                mechanism=(
                    "max-snippet caps how much text may be used as a direct input for AI "
                    "Overviews and AI Mode, so a low value truncates the quotable answer."
                ),
                impact="An assistant may have too little text to state a complete fact.",
                observation=(
                    f"{len(limited)} of {total} content page(s) set max-snippet to "
                    + ", ".join(sorted({str(item.max_snippet) for item in limited}))
                    + " characters."
                ),
                source_urls=[item.url for item in limited[:8]],
                metrics={"pages_checked": total, "pages_limited": len(limited)},
                action_summary=(
                    "Raise max-snippet, or use max-snippet:-1 for no limit, on pages that "
                    "should be quotable."
                ),
                rationale=(
                    "max-snippet:-1 means unlimited and is not counted; only low positive "
                    "values are reported."
                ),
                confidence=0.9,
                scope_pages=len(limited),
                scope_fraction=len(limited) / total,
                impact_weight=2,
            )
        )

    hidden = [item for item in policies if item.data_nosnippet_dominant]
    if hidden:
        worst = max(hidden, key=lambda item: item.data_nosnippet_fraction)
        findings.append(
            make_finding(
                id="CR-022",
                category="crawlability",
                title="data-nosnippet covers most of the page body",
                mechanism_code="data_nosnippet_hides_body",
                mechanism=(
                    "data-nosnippet excludes the wrapped elements from snippets. Applied to a "
                    "byline or a price that is routine; applied to the body it becomes a "
                    "page-level opt-out."
                ),
                impact="The substance of the page cannot be excerpted or cited.",
                observation=(
                    f"{len(hidden)} of {total} content page(s) wrap at least "
                    f"{int(DATA_NOSNIPPET_DOMINANT * 100)}% of their visible text in "
                    f"data-nosnippet (worst: {worst.data_nosnippet_fraction:.0%} on {worst.url})."
                ),
                source_urls=[item.url for item in hidden[:8]],
                metrics={
                    "pages_checked": total,
                    "worst_fraction": f"{worst.data_nosnippet_fraction:.0%}",
                },
                action_summary=(
                    "Narrow data-nosnippet to the specific elements that must not be quoted, "
                    "rather than the main content region."
                ),
                rationale=(
                    "Targeted use on small elements is expected and is not reported; only "
                    "coverage of the body is."
                ),
                confidence=0.85,
                scope_pages=len(hidden),
                scope_fraction=len(hidden) / total,
                impact_weight=2,
            )
        )

    header_only = [item for item in policies if item.header_only_noindex]
    if header_only:
        findings.append(
            make_finding(
                id="CR-023",
                category="crawlability",
                title="noindex is set in the HTTP header only, not in the markup",
                mechanism_code="noindex_header_only",
                mechanism=(
                    "X-Robots-Tag carries the same directives as the robots meta tag, but is "
                    "invisible to anything that only reads the HTML."
                ),
                impact=(
                    "The page is excluded from indexes while the markup gives no sign of it, "
                    "so the exclusion is easy to miss and often unintended."
                ),
                observation=(
                    f"{len(header_only)} of {total} content page(s) return noindex in the "
                    "X-Robots-Tag response header with no matching robots meta tag."
                ),
                source_urls=[item.url for item in header_only[:8]],
                metrics={
                    "pages_checked": total,
                    "header_values": ", ".join(
                        sorted({str(item.x_robots_tag) for item in header_only})[:4]
                    ),
                },
                action_summary=(
                    "Remove noindex from the X-Robots-Tag header on public pages, or mirror it "
                    "in the markup so the intent is visible."
                ),
                action_details=(
                    "Header directives are usually added by a CDN, reverse proxy, or framework "
                    "middleware rather than by the page template, which is why they survive "
                    "template changes unnoticed."
                ),
                confidence=0.93,
                scope_pages=len(header_only),
                scope_fraction=len(header_only) / total,
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
    findings.extend(_snippet_findings(snapshot))

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

    rendered_desktop = {
        item.url: item
        for item in snapshot.rendered
        if item.viewport == "desktop" and item.error is None
    }
    gaps = []
    rendered_ok = 0
    for page in success:
        rendered = rendered_desktop.get(page.url) or rendered_desktop.get(page.final_url)
        if not rendered:
            continue
        rendered_ok += 1
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
                    f"{len(gaps)} of {max(rendered_ok, 1)} "
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
                    id="CR-013",
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
                id="CR-014",
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

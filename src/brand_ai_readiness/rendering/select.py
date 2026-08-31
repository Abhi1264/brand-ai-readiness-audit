"""Choose a small representative set of pages to render."""

from __future__ import annotations

from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage, PageRole

_PREFERRED_ROLES: tuple[PageRole, ...] = (
    "homepage",
    "product",
    "service",
    "pricing",
    "about",
    "contact",
    "article",
    "docs",
    "landing",
)


def select_representative_pages(snapshot: CrawlSnapshot, limit: int = 8) -> list[FetchedPage]:
    chosen: list[FetchedPage] = []
    seen: set[str] = set()
    pages = snapshot.successful_pages()
    by_role: dict[str, list[FetchedPage]] = {}
    for page in pages:
        by_role.setdefault(page.role, []).append(page)

    for role in _PREFERRED_ROLES:
        for page in by_role.get(role, []):
            if page.url in seen:
                continue
            chosen.append(page)
            seen.add(page.url)
            break
        if len(chosen) >= limit:
            return chosen[:limit]

    leftovers = sorted(pages, key=lambda item: item.word_count)
    for page in leftovers:
        if page.url in seen:
            continue
        chosen.append(page)
        seen.add(page.url)
        if len(chosen) >= limit:
            break
    return chosen[:limit]

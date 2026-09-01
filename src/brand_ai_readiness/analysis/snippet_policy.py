"""Snippet-suppression directives, from both the HTML and the HTTP response.

Google states that `nosnippet` "will also prevent the content from being used as
a direct input for AI Overviews and AI Mode", and that `max-snippet` "will also
limit how much of the content may be used". These are the most direct on-page
kill switches for AI surfacing that exist, and neither is visible to a checker
that only reads meta tags: the same directives can arrive in the `X-Robots-Tag`
response header, where they are invisible to HTML parsing and can contradict
what the markup says.

`data-nosnippet` is the element-level form. Used on a byline or a price it is
routine; wrapped around the body of a page it silently removes that page from
snippet-based surfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from brand_ai_readiness.analysis.html import visible_text

_MAX_SNIPPET = re.compile(r"max-snippet\s*:\s*(-?\d+)", re.I)

# Below this many characters a snippet cannot carry a useful fact.
LOW_MAX_SNIPPET_CHARS = 50
# data-nosnippet covering more than this share of the page's text stops being a
# targeted exclusion and becomes a page-level opt-out.
DATA_NOSNIPPET_DOMINANT = 0.30


@dataclass
class SnippetPolicy:
    url: str
    meta_robots: str | None = None
    x_robots_tag: str | None = None
    nosnippet: bool = False
    max_snippet: int | None = None
    noindex_in_header: bool = False
    noindex_in_meta: bool = False
    data_nosnippet_chars: int = 0
    page_text_chars: int = 0
    sources: list[str] = field(default_factory=list)

    @property
    def header_only_noindex(self) -> bool:
        """noindex present in the header but absent from the markup.

        This is the case an HTML-only auditor cannot see at all.
        """
        return self.noindex_in_header and not self.noindex_in_meta

    @property
    def max_snippet_is_limiting(self) -> bool:
        # -1 means "no limit" and is the documented default-equivalent.
        if self.max_snippet is None or self.max_snippet < 0:
            return False
        return self.max_snippet <= LOW_MAX_SNIPPET_CHARS

    @property
    def data_nosnippet_fraction(self) -> float:
        if self.page_text_chars <= 0:
            return 0.0
        return min(self.data_nosnippet_chars / self.page_text_chars, 1.0)

    @property
    def data_nosnippet_dominant(self) -> bool:
        return self.data_nosnippet_fraction >= DATA_NOSNIPPET_DOMINANT

    def suppresses_ai_surfaces(self) -> bool:
        return self.nosnippet or self.max_snippet_is_limiting or self.data_nosnippet_dominant


def _directives(value: str | None) -> str:
    return (value or "").lower()


def _max_snippet_from(*values: str | None) -> int | None:
    found: list[int] = []
    for value in values:
        for match in _MAX_SNIPPET.finditer(value or ""):
            try:
                found.append(int(match.group(1)))
            except ValueError:
                continue
    if not found:
        return None
    # A negative value anywhere means unlimited; otherwise the tightest wins.
    if any(item < 0 for item in found):
        return -1
    return min(found)


def _data_nosnippet_chars(soup: BeautifulSoup) -> int:
    total = 0
    for node in soup.find_all(attrs={"data-nosnippet": True}):
        if isinstance(node, Tag):
            total += len(re.sub(r"\s+", " ", node.get_text(" ", strip=True)))
    return total


def analyze_snippet_policy(
    url: str,
    html: str,
    headers: dict[str, str] | None,
    meta_robots: str | None,
) -> SnippetPolicy:
    header_value = None
    for key, value in (headers or {}).items():
        if key.lower() == "x-robots-tag":
            header_value = value
            break

    meta_l = _directives(meta_robots)
    header_l = _directives(header_value)

    soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")
    text = visible_text(soup) if html else ""

    sources: list[str] = []
    if "nosnippet" in meta_l:
        sources.append("meta robots")
    if "nosnippet" in header_l:
        sources.append("X-Robots-Tag header")

    return SnippetPolicy(
        url=url,
        meta_robots=meta_robots,
        x_robots_tag=header_value,
        nosnippet="nosnippet" in meta_l or "nosnippet" in header_l,
        max_snippet=_max_snippet_from(meta_robots, header_value),
        noindex_in_header="noindex" in header_l,
        noindex_in_meta="noindex" in meta_l,
        data_nosnippet_chars=_data_nosnippet_chars(soup),
        page_text_chars=len(text),
        sources=sources,
    )

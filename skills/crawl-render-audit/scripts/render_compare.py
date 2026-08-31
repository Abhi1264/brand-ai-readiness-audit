#!/usr/bin/env python3
"""Compare two HTML files: raw vs rendered."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.html import visible_text, word_count  # noqa: E402
from brand_ai_readiness.models.snapshot import FetchedPage, RenderedPage  # noqa: E402
from brand_ai_readiness.rendering.compare import compare_raw_and_rendered  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare raw HTML vs rendered HTML")
    parser.add_argument("raw_html")
    parser.add_argument("rendered_html")
    parser.add_argument("--url", default="https://example.com/")
    args = parser.parse_args(argv)
    raw = Path(args.raw_html).read_text(encoding="utf-8")
    rendered = Path(args.rendered_html).read_text(encoding="utf-8")
    page = FetchedPage(url=args.url, final_url=args.url, html=raw, text=visible_text(raw), word_count=word_count(visible_text(raw)))
    rendered_page = RenderedPage(url=args.url, html=rendered, visible_text=visible_text(rendered), viewport="desktop")
    gap = compare_raw_and_rendered(page, rendered_page)
    print(
        json.dumps(
            {
                "url": gap.url,
                "raw_words": gap.raw_words,
                "rendered_words": gap.rendered_words,
                "facts_only_in_render": gap.facts_only_in_render,
                "meaningful": gap.meaningful,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

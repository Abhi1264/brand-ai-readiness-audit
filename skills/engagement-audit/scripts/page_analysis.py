#!/usr/bin/env python3
"""Homepage orientation signals from an HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.engagement import homepage_orientation  # noqa: E402
from brand_ai_readiness.analysis.html import visible_text, word_count  # noqa: E402
from brand_ai_readiness.models.snapshot import FetchedPage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Homepage orientation analysis")
    parser.add_argument("html_file")
    parser.add_argument("--url", default="https://example.com/")
    args = parser.parse_args(argv)
    html = Path(args.html_file).read_text(encoding="utf-8")
    text = visible_text(html)
    page = FetchedPage(
        url=args.url,
        final_url=args.url,
        html=html,
        text=text,
        word_count=word_count(text),
        role="homepage",
    )
    print(json.dumps(homepage_orientation(page), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

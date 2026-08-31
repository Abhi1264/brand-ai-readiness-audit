#!/usr/bin/env python3
"""Extract freshness signals from an HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import get_args

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.freshness import page_freshness  # noqa: E402
from brand_ai_readiness.analysis.html import visible_text, word_count  # noqa: E402
from brand_ai_readiness.models.snapshot import FetchedPage, PageRole  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freshness signals from HTML")
    parser.add_argument("html_file")
    parser.add_argument("--url", default="https://example.com/page")
    parser.add_argument("--role", default="article")
    args = parser.parse_args(argv)
    html = Path(args.html_file).read_text(encoding="utf-8")
    text = visible_text(html)
    role = args.role if args.role in get_args(PageRole) else "article"
    page = FetchedPage(
        url=args.url,
        final_url=args.url,
        html=html,
        text=text,
        word_count=word_count(text),
        role=role,
    )
    signal = page_freshness(page)
    print(
        json.dumps(
            {
                "status": signal.status,
                "date_published": signal.date_published,
                "date_modified": signal.date_modified,
                "visible_date": signal.visible_date,
                "copyright_year": signal.copyright_year,
                "time_sensitive": signal.time_sensitive,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

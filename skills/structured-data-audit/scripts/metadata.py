#!/usr/bin/env python3
"""Extract Open Graph and meta description from HTML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.html import meta_content, open_graph, parse_html  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract OG/meta tags")
    parser.add_argument("html_file")
    args = parser.parse_args(argv)
    soup = parse_html(Path(args.html_file).read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "open_graph": open_graph(soup),
                "description": meta_content(soup, "description"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

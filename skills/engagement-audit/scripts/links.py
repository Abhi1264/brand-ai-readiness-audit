#!/usr/bin/env python3
"""List internal/external links from an HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.html import extract_links, parse_html  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract links from HTML")
    parser.add_argument("html_file")
    parser.add_argument("--url", default="https://example.com/")
    args = parser.parse_args(argv)
    soup = parse_html(Path(args.html_file).read_text(encoding="utf-8"))
    internal, external = extract_links(soup, args.url)
    print(json.dumps({"internal": internal, "external": external}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check whether a URL is allowed by a robots.txt document."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.crawler.robots import allows_url  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="robots.txt allow/deny check")
    parser.add_argument("robots_file", help="Path to a robots.txt file")
    parser.add_argument("url")
    args = parser.parse_args(argv)
    raw = Path(args.robots_file).read_text(encoding="utf-8")
    allowed = allows_url(raw, args.url)
    print("allow" if allowed else "disallow")
    return 0 if allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())

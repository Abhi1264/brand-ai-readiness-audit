#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.site_type import expected_schema_types  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expected schema.org types for a site class")
    parser.add_argument("site_type")
    args = parser.parse_args(argv)
    print(json.dumps({"site_type": args.site_type, "expected": expected_schema_types(args.site_type)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

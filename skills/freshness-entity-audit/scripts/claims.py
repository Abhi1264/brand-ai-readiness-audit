#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.claims import extract_claims  # noqa: E402
from brand_ai_readiness.models.snapshot import CrawlSnapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract on-page claims from a snapshot")
    parser.add_argument("snapshot_json")
    args = parser.parse_args(argv)
    snapshot = CrawlSnapshot.model_validate(json.loads(Path(args.snapshot_json).read_text(encoding="utf-8")))
    extract_claims(snapshot)
    print(json.dumps([item.model_dump() for item in snapshot.claims], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate a report JSON file against the contest schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.orchestration.validate import validate_report_payload  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an audit report JSON file")
    parser.add_argument("report", help="Path to report JSON")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    report = validate_report_payload(payload)
    print(f"OK: {report.site} findings={report.summary.total_findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

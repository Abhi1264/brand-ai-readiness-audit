#!/usr/bin/env python3
"""Build the submission zip.

The marketplace root is this repository, so the zip must contain
marketplace.json at its root plus everything needed to actually run the audit.

This uses an ALLOWLIST rather than a list of things to skip. A denylist fails
open: anything not explicitly named -- a stray virtualenv, a downloaded model,
a scratch directory -- ships silently, and the submission has a hard 50 MB cap.
An allowlist fails closed, which is the safe direction for a deadline.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brand-ai-readiness-audit.zip"

MAX_ZIP_MB = 50.0

# Top-level entries that belong in the marketplace, and why.
INCLUDE = {
    "marketplace.json": "required manifest, must sit at the zip root",
    "README.md": "required by the brief: describes each skill and the entrypoint",
    "LICENSE": "license referenced by every SKILL.md",
    "skills": "the skills themselves",
    "src": "the implementation the skill scripts import",
    "examples": "sample report showing the output contract",
    "tests": "fixture sites and checks that evidence the detection logic",
    "scripts": "this packaging script",
    "pyproject.toml": "dependency and packaging metadata",
    "requirements.txt": "pinned runtime dependencies",
}

# Deliberately excluded, and why. Kept explicit so the reasoning survives.
EXCLUDE_NOTES = {
    "design-system": "UI design system for the local web viewer; not part of the marketplace",
    "app.py": "Vercel entrypoint for the optional web viewer",
    "vercel.json": "deployment config",
    ".vercelignore": "deployment config",
    ".env.example": "only documents the optional LLM polish; no key is required",
    ".gitignore": "repository hygiene, not marketplace content",
}

SKIP_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".playwright", ".vercel", "htmlcov", "dist", "build",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".zip", ".log"}


def _wanted(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel.parts[0] not in INCLUDE:
        return False
    if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
        return False
    if path.name == ".DS_Store" or path.suffix in SKIP_SUFFIXES:
        return False
    if path.name.startswith(".env"):
        return False
    return True


def collect() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and _wanted(p))


def main() -> int:
    files = collect()
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())

    names = zipfile.ZipFile(OUT).namelist()
    if "marketplace.json" not in names:
        raise SystemExit("marketplace.json missing from ZIP root")
    for skill in ("audit-orchestrator", "crawl-render-audit", "structured-data-audit",
                  "freshness-entity-audit", "engagement-audit"):
        if f"skills/{skill}/SKILL.md" not in names:
            raise SystemExit(f"skills/{skill}/SKILL.md missing from ZIP")

    size_mb = OUT.stat().st_size / (1024 * 1024)
    if size_mb > MAX_ZIP_MB:
        OUT.unlink()
        raise SystemExit(f"ZIP is {size_mb:.1f} MB, over the {MAX_ZIP_MB:.0f} MB submission cap")

    excluded = sorted(p.name for p in ROOT.iterdir() if p.name in EXCLUDE_NOTES)
    print(f"Wrote {OUT} ({len(names)} files, {size_mb:.2f} MB / {MAX_ZIP_MB:.0f} MB cap)")
    if excluded:
        print("Excluded by design: " + ", ".join(excluded))
    unknown = sorted(
        p.name for p in ROOT.iterdir()
        if p.name not in INCLUDE and p.name not in EXCLUDE_NOTES
        and not p.name.startswith(".") and p.name != OUT.name
    )
    if unknown:
        print(f"NOTE: not in the allowlist, so NOT shipped: {', '.join(unknown)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

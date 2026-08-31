#!/usr/bin/env python3
"""Build brand-ai-readiness-audit.zip with marketplace.json at the archive root."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brand-ai-readiness-audit.zip"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".playwright",
    "htmlcov",
    "dist",
    "build",
    ".egg-info",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".zip", ".log"}
SKIP_FILES = {".DS_Store"}


def should_skip(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in rel_parts):
        return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    if path.name.startswith(".env") and path.name != ".env.example":
        return True
    return False


def main() -> int:
    files = [p for p in ROOT.rglob("*") if p.is_file() and not should_skip(p)]
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    names = zipfile.ZipFile(OUT).namelist()
    if "marketplace.json" not in names:
        raise SystemExit("marketplace.json missing from ZIP root")
    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"Wrote {OUT} ({len(names)} files, {size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

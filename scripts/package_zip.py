#!/usr/bin/env python3
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brand-ai-readiness-audit.zip"
MAX_ZIP_MB = 50.0

INCLUDE = frozenset({
    "marketplace.json",
    "README.md",
    "JURY-INSTRUCTIONS.md",
    "run-jury.sh",
    "LICENSE",
    "skills",
    "src",
    "examples",
    "tests",
    "scripts",
    "pyproject.toml",
    "requirements.txt",
})
EXCLUDE = frozenset({
    "design-system",
    "app.py",
    "vercel.json",
    ".vercelignore",
    ".env.example",
    ".gitignore",
})
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

    excluded = sorted(p.name for p in ROOT.iterdir() if p.name in EXCLUDE)
    print(f"Wrote {OUT} ({len(names)} files, {size_mb:.2f} MB / {MAX_ZIP_MB:.0f} MB cap)")
    if excluded:
        print("Excluded by design: " + ", ".join(excluded))
    unknown = sorted(
        p.name for p in ROOT.iterdir()
        if p.name not in INCLUDE and p.name not in EXCLUDE
        and not p.name.startswith(".") and p.name != OUT.name
    )
    if unknown:
        print(f"NOTE: not in the allowlist, so NOT shipped: {', '.join(unknown)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

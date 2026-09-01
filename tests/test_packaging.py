from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("package_zip", ROOT / "scripts" / "package_zip.py")
assert _spec and _spec.loader
package_zip = importlib.util.module_from_spec(_spec)
sys.modules["package_zip"] = package_zip
_spec.loader.exec_module(package_zip)


def _shipped() -> set[str]:
    return {p.relative_to(ROOT).as_posix() for p in package_zip.collect()}


def test_manifest_and_every_skill_are_shipped():
    shipped = _shipped()
    assert "marketplace.json" in shipped
    assert "README.md" in shipped
    for skill in (
        "audit-orchestrator",
        "crawl-render-audit",
        "structured-data-audit",
        "freshness-entity-audit",
        "engagement-audit",
    ):
        assert f"skills/{skill}/SKILL.md" in shipped


def test_the_implementation_ships_with_the_skills():
    """Skill scripts import brand_ai_readiness; shipping skills without it is a dead package."""
    shipped = _shipped()
    assert any(path.startswith("src/brand_ai_readiness/") for path in shipped)
    assert "pyproject.toml" in shipped


def test_jury_facing_docs_are_shipped():
    """A judge on a clean machine needs the one command and the caveats."""
    shipped = _shipped()
    assert "JURY-INSTRUCTIONS.md" in shipped
    assert "run-jury.sh" in shipped


def test_deployment_scaffolding_is_not_shipped():
    shipped = _shipped()
    for unwanted in ("app.py", "vercel.json", ".vercelignore", ".env.example"):
        assert unwanted not in shipped
    assert not any(path.startswith("design-system/") for path in shipped)


def test_allowlist_fails_closed_on_unknown_top_level_entries():
    """A denylist ships stray directories silently; this must not.

    A leftover virtualenv or downloaded artifact would otherwise land in a
    submission with a hard 50 MB cap.
    """
    assert ".venv" not in package_zip.INCLUDE
    stray = ROOT / "some-unlisted-scratch-dir" / "big.bin"
    assert not package_zip._wanted(stray)


def test_secrets_are_never_shipped():
    for name in (".env", ".env.local", ".env.production"):
        assert not package_zip._wanted(ROOT / name)


def test_submission_stays_under_the_cap():
    total = sum(p.stat().st_size for p in package_zip.collect())
    assert total / (1024 * 1024) < package_zip.MAX_ZIP_MB

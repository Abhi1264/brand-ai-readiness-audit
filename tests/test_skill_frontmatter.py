from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(p for p in (ROOT / "skills").glob("*/SKILL.md"))

# Top-level `key: value` in the frontmatter block. Indented lines belong to a
# nested mapping (metadata:) and are checked separately.
_TOP_LEVEL = re.compile(r"^([A-Za-z][\w-]*):(.*)$")


def _frontmatter(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").split("\n")
    assert lines[0].strip() == "---", f"{path} must open with a --- frontmatter fence"
    end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    return lines[1:end]


def test_skills_are_discovered():
    assert len(SKILLS) == 5


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_frontmatter_scalars_have_no_unquoted_colon(path: Path):
    """A bare ": " inside an unquoted scalar makes YAML read it as a mapping.

    This silently invalidates the whole SKILL.md against the agentskills.io
    spec while the file still looks fine to a human reader.
    """
    for line in _frontmatter(path):
        match = _TOP_LEVEL.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if not value or value[0] in "\"'|>[{":
            continue  # quoted, block, or nested — YAML handles these
        assert ": " not in value, (
            f"{path.parent.name}/SKILL.md: '{key}' contains an unquoted ': ', "
            f"which YAML parses as a nested mapping. Quote the value or rephrase."
        )


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_required_frontmatter_keys_present(path: Path):
    keys = {m.group(1) for m in (_TOP_LEVEL.match(line) for line in _frontmatter(path)) if m}
    assert {"name", "description", "license"} <= keys


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_name_matches_its_directory(path: Path):
    for line in _frontmatter(path):
        match = _TOP_LEVEL.match(line)
        if match and match.group(1) == "name":
            assert match.group(2).strip() == path.parent.name
            return
    pytest.fail("no name in frontmatter")


def test_manifest_lists_every_skill_with_one_entrypoint():
    import json

    manifest = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))
    listed = {entry["id"] for entry in manifest["skills"]}
    assert listed == {p.parent.name for p in SKILLS}
    entrypoints = [e for e in manifest["skills"] if e.get("entrypoint")]
    assert len(entrypoints) == 1
    for entry in manifest["skills"]:
        assert (ROOT / entry["path"] / "SKILL.md").is_file()

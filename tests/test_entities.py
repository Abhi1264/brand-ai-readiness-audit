from __future__ import annotations

from brand_ai_readiness.analysis.checks_entity import entity_findings
from brand_ai_readiness.analysis.entities import extract_entities, is_under_specified, naming_variants
from brand_ai_readiness.analysis.structured import collect_structured
from tests.helpers import snapshot_from_site_dir


def test_clear_entity_on_excellent_site():
    snapshot = snapshot_from_site_dir("01_excellent")
    collect_structured(snapshot)
    extract_entities(snapshot)
    names = [entity.name.lower() for entity in snapshot.entities]
    assert any("helios" in name for name in names)
    assert naming_variants(snapshot) == []
    assert is_under_specified(snapshot) is False


def test_ambiguous_entity_site():
    snapshot = snapshot_from_site_dir("07_ambiguous_entity")
    collect_structured(snapshot)
    extract_entities(snapshot)
    codes = {item.mechanism_code for item in entity_findings(snapshot)}
    assert "entity_ambiguity" in codes or "missing_entity" in codes


def test_inconsistent_naming_from_conflict_site():
    snapshot = snapshot_from_site_dir("05_conflicting_structured")
    collect_structured(snapshot)
    extract_entities(snapshot)
    variants = naming_variants(snapshot)
    assert variants

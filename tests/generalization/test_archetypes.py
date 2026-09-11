from __future__ import annotations

import pytest

from brand_ai_readiness.analysis.site_type import expected_schema_types
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from tests.helpers import snapshot_from_site_dir

# fixture directory -> inferred site type
ARCHETYPES = {
    "arch_ecommerce": "ecommerce",
    "arch_blog": "article",
    "arch_local": "local_business",
    "arch_docs": "docs",
}

# Markup that would be wrong to demand of a given archetype.
INAPPROPRIATE = {
    "arch_ecommerce": {"LocalBusiness", "TechArticle", "CollegeOrUniversity"},
    "arch_blog": {"LocalBusiness", "Product", "Offer"},
    "arch_local": {"Product", "Offer", "TechArticle"},
    "arch_docs": {"LocalBusiness", "Product", "Offer"},
}


def _report(directory: str):
    return report_from_snapshot(snapshot_from_site_dir(directory))


@pytest.mark.parametrize("directory,expected", ARCHETYPES.items())
def test_site_type_is_inferred_correctly(directory: str, expected: str):
    assert _report(directory).site_type == expected


@pytest.mark.parametrize("directory", ARCHETYPES)
def test_a_healthy_site_raises_nothing_severe(directory: str):
    severe = [f for f in _report(directory).findings if f.severity in {"critical", "high"}]
    assert not severe, [f"{f.severity}: {f.title}" for f in severe]


@pytest.mark.parametrize("directory", ARCHETYPES)
def test_no_markup_is_demanded_that_the_archetype_does_not_need(directory: str):
    report = _report(directory)
    text = " ".join(
        f.title + " " + (f.suggested_action.summary or "") for f in report.findings
    ) + " ".join(
        r.summary + " " + r.what_to_change for r in report.proactive_recommendations
    )
    for wrong in INAPPROPRIATE[directory]:
        assert wrong not in text, f"{directory} was told to add {wrong}"


@pytest.mark.parametrize("directory,expected", ARCHETYPES.items())
def test_expected_schema_matches_the_archetype(directory: str, expected: str):
    types = expected_schema_types(_report(directory).site_type)
    assert "Organization" in types and "WebSite" in types
    if expected == "ecommerce":
        assert "Product" in types
    if expected == "local_business":
        assert "LocalBusiness" in types
    if expected == "article":
        assert "Article" in types


def test_local_business_markup_satisfies_the_organization_requirement():
    codes = {f.mechanism_code for f in _report("arch_local").findings}
    assert "missing_organization" not in codes


def test_identity_is_recognised_when_the_brand_is_the_subject():
    codes = {f.mechanism_code for f in _report("arch_docs").findings}
    assert "weak_homepage_orientation" not in codes


def test_the_auditor_discriminates_between_archetypes():
    inferred = {d: _report(d).site_type for d in ARCHETYPES}
    assert len(set(inferred.values())) == len(ARCHETYPES), inferred


def test_defective_sites_are_still_caught():
    broken = _report("04_missing_structured")
    assert any(f.severity in {"critical", "high"} for f in broken.findings)
    thin = _report("10_strong_disco_weak_engagement")
    assert any(f.category == "engagement" for f in thin.findings)

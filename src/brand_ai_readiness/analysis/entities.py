"""Entity extraction and consistency — site signals only, no speculative resolution."""

from __future__ import annotations

import re

from brand_ai_readiness.models.snapshot import CrawlSnapshot, EntityRecord

_ORG_STOP = {
    "home",
    "welcome",
    "blog",
    "news",
    "contact",
    "privacy",
    "terms",
    "login",
    "docs",
}


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" |-")


def _same_as_values(data: dict[str, object]) -> list[str]:
    values: list[str] = []
    for key in ("sameAs", "sameas"):
        value = data.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
    return values


def extract_entities(snapshot: CrawlSnapshot) -> CrawlSnapshot:
    names: list[tuple[str, str, str, list[str]]] = []
    locations: list[str] = []
    products: list[tuple[str, str]] = []

    for block in snapshot.structured:
        name = block.data.get("name")
        types = {item.lower() for item in block.types}
        if isinstance(name, str) and name.strip():
            org_types = {"organization", "localbusiness", "ngo", "corporation", "brand", "collegeoruniversity", "website"}
            if any("product" in item or "software" in item for item in types):
                kind = "product"
            elif any("person" in item for item in types):
                kind = "person"
            elif any("place" in item or "address" in item or "localbusiness" in item for item in types):
                kind = "location"
            elif any(item in org_types for item in types) or not types:
                kind = "organization"
            else:
                continue
            names.append((name.strip(), kind, block.url, _same_as_values(block.data)))

    homepage = snapshot.homepage()
    if homepage:
        og_site = None
        for block in snapshot.structured:
            if block.url == homepage.url and block.kind == "opengraph":
                og_site = block.data.get("og:site_name") or block.data.get("og:title")
        title = homepage.title or ""
        brand = title.split("|")[0].split("—")[0].split("-")[0].strip()
        if brand and brand.lower() not in _ORG_STOP and 2 <= len(brand) <= 80:
            names.append((brand, "brand", homepage.url, []))
        if isinstance(og_site, str) and og_site.strip():
            names.append((og_site.strip(), "organization", homepage.url, []))
        loc = re.search(
            r"\b(?:in|based in|headquartered in|located in)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
            homepage.text or "",
        )
        if loc:
            locations.append(loc.group(1))

    for page in snapshot.pages_by_role("product") + snapshot.pages_by_role("service"):
        if page.title:
            products.append((_clean_name(page.title.split("|")[0]), page.url))

    grouped: dict[str, EntityRecord] = {}
    for name, kind, url, same_as in names:
        key = name.lower()
        record = grouped.get(key)
        if record is None:
            record = EntityRecord(name=name, kind=kind, sources=[url], same_as=list(same_as))
            grouped[key] = record
        else:
            if url not in record.sources:
                record.sources.append(url)
            if kind != record.kind and kind == "organization":
                record.kind = "organization"
            for item in same_as:
                if item not in record.same_as:
                    record.same_as.append(item)
    for name, url in products:
        key = name.lower()
        if key not in grouped:
            grouped[key] = EntityRecord(name=name, kind="product", sources=[url])
    for location in locations:
        grouped.setdefault(
            location.lower(),
            EntityRecord(name=location, kind="location", sources=[homepage.url if homepage else snapshot.start_url]),
        )
    snapshot.entities = list(grouped.values())
    return snapshot


def organization_names(snapshot: CrawlSnapshot) -> list[str]:
    return [
        entity.name
        for entity in snapshot.entities
        if entity.kind in {"organization", "brand"}
    ]


def naming_variants(snapshot: CrawlSnapshot) -> list[str]:
    orgs = organization_names(snapshot)
    normalized = [_clean_name(name) for name in orgs]
    unique = list(dict.fromkeys(normalized))
    if len(unique) <= 1:
        return []
    # Treat "Acme" and "Acme Inc" as compatible, not conflicting.
    stems = {
        re.sub(r"\b(inc|llc|ltd|corp|corporation|co)\b\.?", "", name, flags=re.I).strip().lower()
        for name in unique
    }
    stems.discard("")
    if len(stems) <= 1:
        return []
    shortest = min(stems, key=len)
    if shortest and all(shortest in stem for stem in stems):
        return []
    return unique


def is_under_specified(snapshot: CrawlSnapshot) -> bool:
    """Ambiguity only if the site's own signals are thin."""
    orgs = [entity for entity in snapshot.entities if entity.kind in {"organization", "brand"}]
    if not orgs:
        return False
    primary = min(orgs, key=lambda item: len(item.name))
    name = primary.name.strip()
    tokens = name.split()
    weak_words = {"the", "group", "labs", "studio", "digital", "global", "systems", "solutions", "co"}
    generic = (len(tokens) == 1 or (len(tokens) == 2 and any(tok.lower() in weak_words for tok in tokens))) and not re.search(
        r"\d", name
    )
    homepage = snapshot.homepage()
    text = homepage.text if homepage else ""
    has_industry = bool(
        re.search(
            r"\b(software|agency|university|clinic|restaurant|bank|nonprofit|"
            r"manufacturer|manufacturers|robotics|insurance|apparel|analytics|healthcare)\b",
            text,
            re.I,
        )
    )
    has_place = any(entity.kind == "location" for entity in snapshot.entities)
    has_same_as = any(entity.same_as for entity in orgs)
    has_legal = bool(re.search(r"\b(inc|llc|ltd|corp|limited|gmbh)\b", " ".join(organization_names(snapshot)), re.I))
    disambiguators = sum([has_industry, has_place, has_same_as, has_legal])
    return generic and disambiguators < 2

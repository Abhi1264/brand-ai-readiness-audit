# Freshness checks

## Signals (in order)

1. JSON-LD `dateModified` / `datePublished`
2. `article:modified_time` / `article:published_time`
3. Visible "Updated" / "Published" dates
4. Copyright year — **recorded, never used as a modification date**

## Findings

- `stale_time_sensitive`: parsed date older than two years **and** time-sensitive language
- `freshness_unknown`: pricing/article page is time-sensitive and has no usable date

No date on an evergreen corporate page is not a defect.

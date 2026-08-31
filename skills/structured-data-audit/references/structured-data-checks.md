# Structured data checks

## Parse

- `application/ld+json` (including `@graph`)
- `og:*` meta
- `meta name=description`
- canonical (cross-checked with crawl skill)

## Site-type expectations

Only recommend types that fit observed content.

| Inferred type | Useful types |
| --- | --- |
| ecommerce | Organization, Product, Offer, BreadcrumbList |
| article | Organization, Article, BreadcrumbList |
| local_business | LocalBusiness, PostalAddress, Organization |
| saas / corporate | Organization, WebSite |
| university | CollegeOrUniversity or Organization |
| nonprofit | NGO or Organization |
| docs | WebSite, TechArticle (optional) |

## Consistency

Mismatch if structured name/price is not found in visible text or title, after allowing partial token overlap.

Malformed JSON-LD is always worth reporting when observed.

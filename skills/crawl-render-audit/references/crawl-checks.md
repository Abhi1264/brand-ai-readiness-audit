# Crawl and render checks

## Always collect

- robots.txt availability and the Disallow patterns that actually matched audited URLs
- HTTP status and redirect chain
- content-type
- canonical href vs fetched URL
- robots meta / noindex
- sitemap loc entries
- internal links
- raw visible-text word count
- rendered word count when a browser is available

## Emit a finding only if

| Signal | Finding |
| --- | --- |
| Important URL disallowed | robots blocks important pages |
| Important URL 4xx/5xx | HTTP failure |
| redirect_loop / excessive_redirects | redirect failure |
| noindex on homepage/product/about | noindex important |
| sitemap listed but unusable | sitemap inaccessible |
| meaningful render gap | JS content gap |
| fact-like alt/canvas without text | image-only facts |
| linked 404/410 | broken internal links |

## Do not emit

- "robots.txt exists"
- "the site uses JavaScript"
- "images exist"
- "we only crawled N pages, therefore the whole site lacks X" without stating N

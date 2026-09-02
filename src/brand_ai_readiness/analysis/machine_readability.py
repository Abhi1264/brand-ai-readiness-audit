from __future__ import annotations

import re

from brand_ai_readiness.analysis.html import has_canvas_or_embed, image_alts, parse_html, prices_in_text
from brand_ai_readiness.models.snapshot import FetchedPage

_FACTISH_ALT = re.compile(
    r"(\$|€|£|₹|\d[\d,]*\.\d{2}|price|pricing|founded|ceo|headquarters|rating)",
    re.I,
)


def image_only_fact_pages(pages: list[FetchedPage]) -> list[dict[str, object]]:
    flagged: list[dict[str, object]] = []
    important_roles = {"product", "pricing", "homepage"}
    for page in pages:
        text_prices = prices_in_text(page.text)
        need_alts = not text_prices
        need_canvas = page.word_count < 40
        need_img = page.word_count < 25 and page.role in important_roles
        if not need_alts and not need_canvas and not need_img:
            continue
        soup = parse_html(page.html)
        counts = has_canvas_or_embed(soup)
        alts = image_alts(soup) if need_alts else []
        alt_facts = [alt for alt in alts if _FACTISH_ALT.search(alt)]
        text = page.text or ""
        if alt_facts and not text_prices:
            missing_in_text = [alt for alt in alt_facts if alt.lower() not in text.lower()]
            if missing_in_text:
                flagged.append(
                    {
                        "url": page.url,
                        "reason": "image_alt_facts_absent_from_text",
                        "alts": missing_in_text[:5],
                        "word_count": page.word_count,
                    }
                )
                continue
        if counts["canvas"] and page.word_count < 40:
            flagged.append(
                {
                    "url": page.url,
                    "reason": "canvas_with_almost_no_text",
                    "counts": counts,
                    "word_count": page.word_count,
                }
            )
            continue
        if page.word_count < 25 and counts["img"] >= 3 and page.role in important_roles:
            flagged.append(
                {
                    "url": page.url,
                    "reason": "important_page_image_heavy_little_text",
                    "counts": counts,
                    "word_count": page.word_count,
                }
            )
    return flagged

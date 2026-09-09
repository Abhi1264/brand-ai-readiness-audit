# Example output

Both files are **real output**, not hand-written. They are produced by auditing the bundled
fixture site at `tests/fixtures/sites/04_missing_structured/`, so a reader can regenerate them
and get the same thing, and no claim is made about anyone's live website.

| File | What it is |
| --- | --- |
| `sample-report.json` | The report contract. This is what the entrypoint emits. |
| `sample-report.md` | The same data rendered for a human reader (`--format markdown`). |
| `sample-evidence.json` | A single finding's evidence payload before it is flattened into prose. |

## Regenerate them

```bash
python3 -m http.server 8877 --directory tests/fixtures/sites/04_missing_structured &
python -m brand_ai_readiness http://127.0.0.1:8877/ --no-render --max-pages 10 \
  -o examples/sample-report.json
python -m brand_ai_readiness http://127.0.0.1:8877/ --no-render --max-pages 10 \
  --format markdown -o examples/sample-report.md
kill %1
```

The `site` field reads `127.0.0.1` because that is genuinely where the fixture was served from.
Rendering is disabled so the output does not depend on whether Playwright is installed.

## Why this fixture

It carries a representative spread rather than a single defect: missing structured data, an
important page returning a non-2xx status, broken internal links, absent Open Graph metadata, and
a homepage that never states who the offering is for — across the crawlability, structured-data
and engagement concerns, at three different severities, plus proactive recommendations where no
defect was found.

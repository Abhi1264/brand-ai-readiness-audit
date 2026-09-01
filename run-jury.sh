#!/usr/bin/env bash
# One-command setup, test, and audit. Usage: ./run-jury.sh [url]
set -euo pipefail

URL="${1:-https://example.com}"
PY="${PYTHON:-python3}"
VENV=".venv"

echo "==> Creating virtualenv"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"

echo "==> Installing dependencies"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e ".[dev]"

echo "==> Running test suite"
"$VENV/bin/python" -m pytest -q

echo "==> Auditing $URL"
"$VENV/bin/python" -m brand_ai_readiness "$URL" -o audit-report.json

echo "==> Validating the report against the required schema"
"$VENV/bin/python" skills/audit-orchestrator/scripts/validate_report.py audit-report.json

echo
echo "==> Summary"
"$VENV/bin/python" - <<'PYEOF'
import json
r = json.load(open("audit-report.json"))
s = r["summary"]
print(f"  {r['site']}  site_type={r.get('site_type')}  audited_at={r['audited_at']}")
print(f"  findings: {s['total_findings']}  "
      f"critical={s['critical']} high={s['high']} medium={s['medium']} low={s.get('low', 0)}")
cov = r.get("coverage", {})
print(f"  crawled {cov.get('pages_crawled')} of {cov.get('pages_discovered')} discovered  "
      f"rendering={cov.get('rendering_status')}  probe={cov.get('access_probe_status')}")
for f in r["findings"][:5]:
    print(f"    [{f['severity']:8}] {f['title']}")
if len(r["findings"]) > 5:
    print(f"    ... and {len(r['findings']) - 5} more in audit-report.json")
for line in cov.get("limitations", []):
    print(f"  limitation: {line}")
PYEOF
echo
echo "Full report: audit-report.json"

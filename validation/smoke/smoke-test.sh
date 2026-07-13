#!/usr/bin/env bash
# smoke-test.sh — post-install CLI smoke tests.
# Run after `brew install earlbear` to verify all tools are on PATH.
# No credentials needed — just checks binaries are callable.

set -uo pipefail

PASS=0; FAIL=0

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

check() {
    local name="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++)) || true
    else
        local exit_code=$?
        # Exit code 2 = CONFIG_MISSING is expected (no .env) — still a pass
        if [ "$exit_code" -eq 2 ]; then
            echo -e "  ${GREEN}✓${NC} $name (CONFIG_MISSING — expected)"
            ((PASS++)) || true
        else
            echo -e "  ${RED}✗${NC} $name (exit $exit_code)"
            ((FAIL++)) || true
        fi
    fi
}

echo "EarlBear CLI smoke tests"
echo "────────────────────────"

check "ebdeck --help"   ebdeck --help
check "ebjira"         ebjira issue list
check "ebdocs"         ebdocs doc list
check "ebshop"         ebshop shop info
check "ebtranscripts --help" ebtranscripts --help
check "ebtranscripts self-test" ebtranscripts sanitize --self-test
check "agent-cli exists" test -x "$(command -v agent-cli)"
check "earlbear-setup exists" test -x "$(command -v earlbear-setup)"

echo ""
echo "────────────────────────"
echo "Results: $PASS passed, $FAIL failed"

[ "$FAIL" -eq 0 ]

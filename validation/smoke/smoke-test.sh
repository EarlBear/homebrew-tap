#!/usr/bin/env bash
# smoke-test.sh — every command the tap installs answers --help (Tier 4; rebrand step 1.5, test 8).
#
# For each formula in the tap's Formula/ folder, every command its install linked into bin/ must
#   - exit 0 on `--help`, and
#   - print its own name on standard output.
# "Wrong usage", "no settings yet" and "bad interpreter" all exit non-zero, so none of them passes
# (the old version counted exit 2 as a pass). Standard error is not searched, because a broken
# install's error names the tool too ("bad interpreter: .../ebdeck/...").
#
# Nothing is typed in by name: formulas come from Formula/*.rb and commands from each installed
# formula's bin/ folder, so renaming formulas or commands needs no edit here.
#
# The test controls what each command sees: standard input is empty, each run has a time limit,
# and EARLBEAR_CONFIG_DIR points at a scratch folder holding an empty settings file. So no command
# reads real credentials, and none can write the real settings file (the old set-up wizard ran,
# and touched it, on --help).
#
# Nothing passes by checking nothing: no formulas found fails, a formula that is not installed
# fails, and a formula that installs no command is listed by name.
#
# Settings (environment):
#   SMOKE_FORMULA_DIR   the tap's Formula/ folder. Default: Formula/ beside validation/. The VM
#                       tier pipes this script over ssh, so it sets this.
#   SMOKE_PREFIX        Homebrew's prefix. Default: `brew --prefix`. Point it at fake kegs to test
#                       this script.
#   SMOKE_TIMEOUT       seconds per command. Default 300 (a Docker tool builds its image on its
#                       first run).
#   SMOKE_NO_DOCKER_OK  1 = a command whose formula needs Docker, run while Docker is not running,
#                       is listed as not checked instead of failing. The VM tier has no Docker.

set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'

here="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || pwd)"
FORMULA_DIR="${SMOKE_FORMULA_DIR:-$here/../../Formula}"
PREFIX="${SMOKE_PREFIX:-$(brew --prefix 2>/dev/null)}"
TIMEOUT="${SMOKE_TIMEOUT:-300}"
NO_DOCKER_OK="${SMOKE_NO_DOCKER_OK:-0}"

PASS=0; FAIL=0; UNCHECKED=0; NOCMD=0

work="$(mktemp -d "${TMPDIR:-/tmp}/smoke-test.XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/config"
: > "$work/config/.env"

ok()   { echo -e "  ${GREEN}✓${NC} $*"; PASS=$((PASS + 1)); }
bad()  { echo -e "  ${RED}✗${NC} $*"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}?${NC} $*"; UNCHECKED=$((UNCHECKED + 1)); }
# The first lines of a failed command's errors, or of its output when it wrote no errors.
why()  {
    local f="$1"
    [ -s "$f" ] || f="${1%.err}"
    sed -n '1,3p' "$f" | sed 's/^/      /'
}

# Docker is checked once, and only if a formula needs it.
docker_state=""
docker_running() {
    if [ -z "$docker_state" ]; then
        if docker info >/dev/null 2>&1; then docker_state=up; else docker_state=down; fi
    fi
    [ "$docker_state" = up ]
}

# Run one command with empty stdin, the scratch settings folder and a time limit.
# perl's alarm survives exec, so it also covers wrappers that exec docker.
run_one() {
    local out="$1"; shift
    : > "$work/config/.env"   # a fresh, empty settings file for every command
    EARLBEAR_CONFIG_DIR="$work/config" \
        perl -e 'alarm shift; exec @ARGV or do { print STDERR "cannot run $ARGV[0]: $!\n"; exit 127 }' "$TIMEOUT" "$@" \
        </dev/null >"$out" 2>"$out.err"
}

echo "Installed command smoke tests"
echo "  formulas: $FORMULA_DIR"
echo "  prefix:   ${PREFIX:-<not found>}"
echo "────────────────────────"

if [ -z "$PREFIX" ] || [ ! -d "$PREFIX" ]; then
    bad "Homebrew prefix not found (is brew on PATH? or set SMOKE_PREFIX)"
fi

shopt -s nullglob
formulas=("$FORMULA_DIR"/*.rb)
shopt -u nullglob
if [ "${#formulas[@]}" -eq 0 ]; then
    bad "no formulas found in $FORMULA_DIR (set SMOKE_FORMULA_DIR)"
fi

for rb in "${formulas[@]+"${formulas[@]}"}"; do
    formula="$(basename "$rb" .rb)"
    keg="$PREFIX/opt/$formula"
    if [ ! -d "$keg" ]; then
        bad "$formula: formula not installed ($keg is missing)"
        continue
    fi
    needs_docker=0
    grep -q '^[[:space:]]*depends_on "docker"' "$rb" && needs_docker=1

    found=0
    for cmd in "$keg"/bin/*; do
        [ -e "$cmd" ] || continue
        found=1
        name="$(basename "$cmd")"
        linked="$PREFIX/bin/$name"
        if [ ! -x "$linked" ]; then
            bad "$name ($formula): installed but not linked at $linked"
            continue
        fi
        out="$work/$name.out"
        run_one "$out" "$linked" --help 2>/dev/null   # hides the shell's "Alarm clock" line
        rc=$?
        if [ "$rc" -eq 0 ] && grep -qF -- "$name" "$out"; then
            ok "$name --help ($formula)"
        elif [ "$needs_docker" -eq 1 ] && ! docker_running; then
            if [ "$NO_DOCKER_OK" = "1" ]; then
                skip "$name --help ($formula): not checked, needs Docker, which is not running"
            else
                bad "$name --help ($formula): needs Docker, which is not running (exit $rc)"
            fi
        elif [ "$rc" -eq 142 ]; then
            bad "$name --help ($formula): no answer after ${TIMEOUT}s"
        elif [ "$rc" -ne 0 ]; then
            bad "$name --help ($formula): exit $rc"
            why "$out.err"
        else
            bad "$name --help ($formula): exit 0, but its own name is not in the help it printed"
            why "$out"
        fi
    done
    if [ "$found" -eq 0 ]; then
        echo "  - $formula: installs no command, nothing to run"
        NOCMD=$((NOCMD + 1))
    fi
done

# Checks beyond --help, run only when the command is installed (if it isn't, the loop above has
# already failed its formula).
if [ -x "$PREFIX/bin/ebtranscripts" ]; then
    out="$work/ebtranscripts-self-test.out"
    if run_one "$out" "$PREFIX/bin/ebtranscripts" sanitize --self-test; then
        ok "ebtranscripts sanitize --self-test"
    else
        bad "ebtranscripts sanitize --self-test: exit $?"
        why "$out.err"
    fi
fi

echo ""
echo "────────────────────────"
echo "Results: $PASS passed, $FAIL failed, $UNCHECKED not checked, $NOCMD formulas with no command"

[ "$FAIL" -eq 0 ] && [ "$PASS" -gt 0 ]

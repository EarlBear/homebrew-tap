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
# EARLBEAR_CONFIG_DIR points at a scratch folder holding an empty settings file, and a stand-in
# `security` that finds nothing is first on PATH. So no command reads real credentials (agent-cli
# reads the Keychain before it looks at --help), and none can write the real settings file (the
# old set-up wizard ran, and touched it, on --help).
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
mkdir -p "$work/config" "$work/bin"
: > "$work/config/.env"
# A stand-in macOS `security` that never finds anything, put first on PATH for every run, so no
# command can read a real Keychain entry or pop up a Keychain access prompt nobody will answer.
printf '%s\n' '#!/bin/sh' \
    'echo "security: The specified item could not be found in the keychain." >&2' \
    'exit 44' > "$work/bin/security"
chmod +x "$work/bin/security"

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

# Run one command with empty stdin, the scratch settings folder, the stand-in `security` and a
# time limit. Exits 142 when the time runs out.
# A plain alarm is not enough: the Docker wrappers exec the docker CLI, which catches SIGALRM and
# passes it to the container, where it is ignored. So the command runs in its own process group
# and, on time-out, the whole group (wrapper, docker CLI, a first-run `docker build`) gets SIGKILL.
# A container already started may keep running after that; the test still fails and moves on.
run_one() {
    local out="$1"; shift
    : > "$work/config/.env"   # a fresh, empty settings file for every command
    # agent-cli prefers JIRA_* set in the shell, and the ebjira wrapper forwards them into the
    # container when EBJIRA_USE_SHELL_SETTINGS=1. Clear all five so only the empty .env is read.
    EARLBEAR_CONFIG_DIR="$work/config" PATH="$work/bin:$PATH" \
        env -u JIRA_BASE_URL -u JIRA_USER_EMAIL -u JIRA_PROJECT -u JIRA_API_TOKEN \
            -u EBJIRA_USE_SHELL_SETTINGS \
        perl -e '
            my $t = shift;
            my $pid = fork() // die "fork: $!\n";
            if ($pid == 0) {
                setpgrp(0, 0);
                exec @ARGV or do { print STDERR "cannot run $ARGV[0]: $!\n"; exit 127 };
            }
            $SIG{ALRM} = sub { kill "KILL", -$pid; waitpid $pid, 0; exit 142 };
            alarm $t;
            waitpid $pid, 0;
            exit(($? & 127) ? 128 + ($? & 127) : $? >> 8);
        ' "$TIMEOUT" "$@" \
        </dev/null >"$out" 2>"$out.err"
}

echo "Installed command smoke tests"
echo "  formulas: $FORMULA_DIR"
echo "  prefix:   ${PREFIX:-<not found>}"
echo "────────────────────────"

if [ -z "$PREFIX" ] || [ ! -d "$PREFIX" ]; then
    # Stop here: every formula would otherwise be reported "not installed", burying the cause.
    bad "Homebrew prefix not found (is brew on PATH? or set SMOKE_PREFIX)"
    exit 1
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
    formula_docker=0
    grep -q '^[[:space:]]*depends_on "docker"' "$rb" && formula_docker=1

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
        # A command needs Docker only if its formula says so AND the command itself runs docker
        # (the wrappers do). ebdeck's formula lists Docker, but its --help is plain Python, so its
        # failures must never be put down to Docker being off.
        needs_docker=0
        if [ "$formula_docker" -eq 1 ] && grep -qI 'docker' "$cmd" 2>/dev/null; then
            needs_docker=1
        fi
        out="$work/$name.out"
        run_one "$out" "$linked" --help
        rc=$?
        # The name must appear as a whole word: a renamed `shop` whose help still says `ebshop`
        # must fail, so a plain substring search is not enough.
        if [ "$rc" -eq 0 ] && grep -qw -- "$name" "$out"; then
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
    run_one "$out" "$PREFIX/bin/ebtranscripts" sanitize --self-test
    rc=$?
    if [ "$rc" -eq 0 ]; then
        ok "ebtranscripts sanitize --self-test"
    elif [ "$rc" -eq 142 ]; then
        bad "ebtranscripts sanitize --self-test: no answer after ${TIMEOUT}s"
    else
        bad "ebtranscripts sanitize --self-test: exit $rc"
        why "$out.err"
    fi
fi

echo ""
echo "────────────────────────"
echo "Results: $PASS passed, $FAIL failed, $UNCHECKED not checked, $NOCMD formulas with no command"

[ "$FAIL" -eq 0 ] && [ "$PASS" -gt 0 ]

#!/usr/bin/env bash
# Which Jira settings the ebjira wrapper passes into its container (tap PR #8 review, 2026-11-19).
#
# agent-cli works out each setting (the shell, then the Keychain for the token, then .env), exports
# it and sets EBJIRA_USE_SHELL_SETTINGS=1. Only then does the wrapper pass the shell's values in.
# A plain `ebjira` reads only .env. Stand-in `brew` and `docker` commands print what they were
# asked, so nothing is built or run. Offline, made-up values only.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WRAPPER="$ROOT/wrappers/ebjira/wrapper.sh"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/cfg"
printf '#!/bin/bash\necho stand-in\n' > "$tmp/bin/brew"
printf '#!/bin/bash\n[ "$1" = image ] && exit 0\necho "docker $*"\n' > "$tmp/bin/docker"
chmod +x "$tmp/bin/brew" "$tmp/bin/docker"
printf 'JIRA_BASE_URL=https://file.invalid\n' > "$tmp/cfg/.env"

run() {   # run NAME=value... → sets $out to the docker command line the wrapper built
  out="$(env -u JIRA_BASE_URL -u JIRA_USER_EMAIL -u JIRA_PROJECT -u JIRA_API_TOKEN \
    -u EBJIRA_USE_SHELL_SETTINGS PATH="$tmp/bin:$PATH" EARLBEAR_CONFIG_DIR="$tmp/cfg" \
    "$@" bash "$WRAPPER" issue list 2>&1)"
}

echo "== ebjira wrapper: which settings reach the container =="
run JIRA_API_TOKEN=made-up JIRA_BASE_URL=https://shell.invalid
case "$out" in *"-e JIRA_"*) bad "a plain ebjira passes the shell's settings in ($out)" ;;
  *) ok "a plain ebjira ignores JIRA_* in the shell and reads only .env" ;; esac

run EBJIRA_USE_SHELL_SETTINGS=1 JIRA_API_TOKEN=made-up JIRA_BASE_URL=https://shell.invalid
case "$out" in *"-e JIRA_API_TOKEN"*"-e JIRA_BASE_URL"* | *"-e JIRA_BASE_URL"*"-e JIRA_API_TOKEN"*)
  ok "from agent-cli, the settings it worked out are passed in" ;;
  *) bad "from agent-cli, the settings were not passed in ($out)" ;; esac
case "$out" in *made-up*) bad "the token's value is on the docker command line" ;;
  *) ok "the token is passed by name, so its value is not on the command line" ;; esac
case "$out" in *"-e JIRA_USER_EMAIL"*) bad "a setting that is not set was passed in" ;;
  *) ok "a setting that is not set is not passed in" ;; esac

run EBJIRA_USE_SHELL_SETTINGS=1 JIRA_API_TOKEN=made-up
case "$out" in *"--env-file $tmp/cfg/.env -e JIRA_API_TOKEN"*)
  ok "the passed-in values come after --env-file, so they win over .env" ;;
  *) bad "the passed-in values are not after --env-file ($out)" ;; esac

echo
echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]

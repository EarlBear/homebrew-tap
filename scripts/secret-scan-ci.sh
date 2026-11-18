#!/bin/sh
# Scan the commits a branch adds for secrets. The GitHub check (.github/workflows/secret-scan.yml)
# runs this through `make secret-scan-ci`, and so does a person on the Mac.
#
# Every EarlBear repo has this same file, byte for byte. Change it in all of them at once.
#
# Usage: scripts/secret-scan-ci.sh [BASE]
#   BASE   a commit or branch: scan the commits after it (default origin/main)
#   all    scan every commit HEAD reaches (a manual run, or after a force-push to main)
#
# How it reads merge commits: --diff-merges=remerge shows only what was typed while resolving the
# merge (git 2.36 or later). A key slipped into a conflict fix is caught, and what the merge brought
# in from main is not scanned again under the merge's id. In a merge commit gitleaks names the file
# "b/<path>", so a path rule in .gitleaks.toml may not match there; that adds findings, never hides one.
#
# What this check can't stop:
# - On a pull request, GitHub runs the PR's own copy of this file, the Makefile, the workflow,
#   .gitleaks.toml and .gitleaksignore. A PR that changes any of them can weaken its own scan, and
#   GitHub Free can't pin them to main's copy. A change to any of these files needs a person's
#   sign-off before it merges; the Mac PR review holds such PRs for one.
# - A push to main scans only that push's commits. Main takes only squash merges of pull requests,
#   and each was scanned as a pull request, so a failed run on main is fixed by hand; a later push
#   does not scan it again.
#
# Exit status: 0 nothing found, 1 secrets found, 2 the scan could not run.
set -u

PINNED=8.30.1   # the version the GitHub check installs; keep it the same as the workflow's

base=${1:-origin/main}
case $base in
  -* | *[!A-Za-z0-9._/~^-]*)
    echo "secret-scan-ci: BASE must be a commit, a branch or 'all', not '$base'" >&2
    exit 2 ;;
esac

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "secret-scan-ci: gitleaks is not installed: brew install gitleaks" >&2
  exit 2
fi
version=$(gitleaks version 2>/dev/null)
version=${version#v}
major=${version%%.*}
minor=${version#*.}
minor=${minor%%.*}
case $major.$minor in
  *[!0-9.]* | .* | *.) major=0 minor=0 ;;
esac
if [ "$major" -lt 8 ] || { [ "$major" -eq 8 ] && [ "$minor" -lt 19 ]; }; then
  echo "secret-scan-ci: 'gitleaks git' needs gitleaks 8.19 or later, and this machine has '$version': brew upgrade gitleaks" >&2
  exit 2
fi
if [ "$version" != "$PINNED" ]; then
  echo "secret-scan-ci: note: GitHub runs gitleaks $PINNED and this machine has $version, so the rules can differ" >&2
fi

if [ "$base" = all ]; then
  range=HEAD
else
  range="$base..HEAD"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# No --verbose: it prints the text around each match, and a second secret on the same line would
# show in the log. The findings are listed below from the report instead, without the secret text.
gitleaks git --no-banner --redact --report-format json --report-path "$tmp/report.json" \
  --log-opts="--diff-merges=remerge $range" . 2>"$tmp/log"
status=$?
cat "$tmp/log" >&2

# gitleaks exits 0 and says "no leaks found" when its own `git log` fails, logging the failure
# as ERR. Treat any line logged at level ERR as a scan that did not happen. The log is coloured
# even in a file, so strip the colour codes and look at the level field, not the whole line.
esc=$(printf '\033')
if sed "s/$esc\[[0-9;]*m//g" "$tmp/log" | awk '$2 == "ERR" { found = 1 } END { exit !found }'; then
  echo "secret-scan-ci: gitleaks could not read '$range' (the ERR lines above), so nothing was scanned. Run git fetch, pass a BASE this checkout has, or update git (2.36 or later)." >&2
  exit 2
fi

if [ "$status" -ne 0 ]; then
  if [ -s "$tmp/report.json" ] && command -v jq >/dev/null 2>&1; then
    count=$(jq length "$tmp/report.json")
    if [ "$count" -gt 0 ]; then
      echo "secret-scan-ci: $count secret(s) found in '$range' (the secret text is not shown):" >&2
      # Two secrets on one line share a fingerprint, so list each line once.
      jq -r 'unique_by(.Fingerprint) | .[] | "  \(.File):\(.StartLine)  rule \(.RuleID)  commit \(.Commit[0:12])\n    to accept it, add this line to .gitleaksignore: \(.Fingerprint)"' "$tmp/report.json" >&2
      exit 1
    fi
  elif [ "$status" -eq 1 ] && [ -s "$tmp/report.json" ] && [ "$(head -c 2 "$tmp/report.json")" != "[]" ]; then
    echo "secret-scan-ci: secrets found in '$range'; install jq to list them without the secret text (brew install jq)" >&2
    exit 1
  fi
  echo "secret-scan-ci: gitleaks stopped with exit $status (see its log above)" >&2
  exit 2
fi

echo "secret-scan-ci: no secrets in '$range'"

#!/bin/sh
# Scan the commits a branch adds for secrets. The GitHub check (.github/workflows/secret-scan.yml)
# runs this through `make secret-scan-ci`, and so does a person on the Mac.
#
# Every EarlBear repo has this same file, byte for byte. Change it in all of them at once.
#
# Usage: sh scripts/secret-scan-ci.sh [BASE]
#   BASE   a commit or branch: scan the commits after it (default origin/main)
#   all    scan every commit HEAD reaches (a manual run, or after a force-push to main)
# Run the script itself to see exit 1 and 2 apart: through make, both come back as 2.
#
# How it reads merge commits: --diff-merges=remerge shows only what was typed while resolving the
# merge (git 2.36 or later). A key slipped into a conflict fix is caught, and what the merge brought
# in from main is not scanned again under the merge's id. In a merge commit gitleaks names the file
# "b/<path>", so a path pattern may not match there: an allowlisted path can show up as a finding,
# and a rule that only looks at certain paths (a path pattern starting with ^) can miss a secret.
# git shows no diff at all for a merge of three or more branches, so the scan refuses one.
#
# What this check can't stop:
# - On a pull request, GitHub runs the PR's own copy of this file, the Makefile, the workflow,
#   .gitleaks.toml, .gitleaksignore and .gitattributes. A PR that changes any of them can weaken
#   its own scan (.gitattributes can mark a file as binary, and gitleaks skips binary diffs), and
#   GitHub Free can't pin them to main's copy. A change to any of these files needs a person's
#   sign-off before it merges; the Mac PR review holds such PRs for one.
# - A line that carries the comment gitleaks:allow is skipped. It shows in the PR's diff, so the
#   reviewer is the check there.
# - A commit message with [skip ci] stops GitHub running the check at all for that push.
# - A push to main scans only that push's commits. From 2026-11-18 pull requests reach main as
#   squash merges, each scanned first as a pull request, so a failed run on main is fixed by hand;
#   a later push does not scan it again. (Main's older history has ordinary merge commits too.)
# - A .gitleaksignore line in the form the scan suggests (file:rule:line, no commit id) keeps
#   working after a squash merge, but it also accepts any later secret the same rule finds on that
#   line of that file. That is why .gitleaksignore needs a person's sign-off.
#
# Exit status: 0 nothing found, 1 secrets found, 2 the scan could not run, did not finish, or had
# no commits to scan.
set -u

PINNED=8.30.1   # the version the GitHub check installs; keep it the same as the workflow's

# gitleaks reads .gitleaks.toml and .gitleaksignore from the folder it scans, so scan from the top.
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "secret-scan-ci: not inside a git repository" >&2; exit 2; }
cd "$root" || exit 2

# A config named in the environment would replace the repo's .gitleaks.toml, so the Mac and GitHub
# could scan with different rules. Always use the repo's own.
unset GITLEAKS_CONFIG GITLEAKS_CONFIG_TOML

base=${1:-origin/main}
case $base in
  -* | *[!A-Za-z0-9._/~^@{}+-]*)
    echo "secret-scan-ci: BASE must be a commit, a branch or 'all', not '$base'" >&2
    exit 2 ;;
esac

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "secret-scan-ci: gitleaks is not installed: brew install gitleaks" >&2
  exit 2
fi
version=$(gitleaks version 2>/dev/null)
# The major and minor numbers of a version like 8.30.1 or v8.30.1; empty for anything else.
majmin=$(printf '%s\n' "$version" | sed -n '1s/^v\{0,1\}\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p')
if [ -z "$majmin" ]; then
  echo "secret-scan-ci: can't read the gitleaks version from '$version'; this check needs 8.19 or later: brew upgrade gitleaks" >&2
  exit 2
fi
major=${majmin% *}
minor=${majmin#* }
if [ "$major" -lt 8 ] || { [ "$major" -eq 8 ] && [ "$minor" -lt 19 ]; }; then
  echo "secret-scan-ci: 'gitleaks git' needs gitleaks 8.19 or later, and this machine has '$version': brew upgrade gitleaks" >&2
  exit 2
fi
if [ "${version#v}" != "$PINNED" ]; then
  echo "secret-scan-ci: note: GitHub runs gitleaks $PINNED and this machine has $version, so the rules can differ" >&2
fi

if [ "$base" = all ]; then
  range=HEAD
else
  range="$base..HEAD"
fi

# gitleaks exits 0 and says "no leaks found" when its own `git log` fails. Run the same `git log`
# first, so a range this checkout can't read (or a git older than 2.36) stops here.
if ! git log -1 --format=%H --diff-merges=remerge "$range" -- >/dev/null; then
  echo "secret-scan-ci: git cannot list '$range' in this checkout, so nothing would be scanned. Run git fetch, pass a BASE this checkout has, or update git (2.36 or later)." >&2
  exit 2
fi
commits=$(git rev-list --count "$range" --)
# No commits would pass as a clean scan, which hides a wrong or lost BASE. Say so and stop.
case $commits in
  '' | *[!0-9]* | 0)
    echo "secret-scan-ci: '$range' holds no commits, so there is nothing to scan. Pass a BASE before the commits you mean, or 'all'." >&2
    exit 2 ;;
esac

octopus=$(git rev-list --min-parents=3 "$range" -- | head -n 1)
if [ -n "$octopus" ]; then
  echo "secret-scan-ci: commit $octopus merges three or more branches, and git shows no diff for it, so it can't be scanned" >&2
  exit 2
fi

tmp=$(mktemp -d) || { echo "secret-scan-ci: could not make a temporary folder" >&2; exit 2; }
trap 'rm -rf "$tmp"' EXIT
# Stopped part way (Ctrl-C reaches gitleaks too, and this runs once it ends): show what gitleaks
# logged, and exit 2.
trap 'cat "$tmp/log" >&2 2>/dev/null; echo "secret-scan-ci: stopped before the scan finished" >&2; exit 2' INT TERM

# No --verbose: it prints the text around each match, and a second secret on the same line would
# show in the log. The findings are listed below from the report instead, without the secret text.
gitleaks git --no-banner --redact --report-format json --report-path "$tmp/report.json" \
  --log-opts="--diff-merges=remerge $range" . 2>"$tmp/log"
status=$?
cat "$tmp/log" >&2

# gitleaks logs git's own failures at level ERR, and still says "no leaks found". The log is
# coloured even in a file, so strip the colour codes and look at the level field.
esc=$(printf '\033')
logged_err=no
if sed "s/$esc\[[0-9;]*m//g" "$tmp/log" | awk '$2 == "ERR" { found = 1 } END { exit !found }'; then
  logged_err=yes
fi

# A secret in the report is real whatever else went wrong, so findings are listed before the ERR
# lines are judged. Two secrets on one line share a fingerprint, so count and list each line once.
if [ -s "$tmp/report.json" ]; then
  if command -v jq >/dev/null 2>&1; then
    count=$(jq 'unique_by(.Fingerprint) | length' "$tmp/report.json" 2>/dev/null)
    # A report jq can't read must not pass as "nothing found".
    case $count in
      '' | *[!0-9]*)
        echo "secret-scan-ci: jq could not read gitleaks' report, so the findings can't be listed; the scan did not finish" >&2
        exit 2 ;;
    esac
    if [ "$count" -gt 0 ]; then
      echo "secret-scan-ci: secrets found on $count line(s) in '$range' (the secret text is not shown):" >&2
      # A fingerprint without the commit id still matches after a squash merge gives the line a
      # new commit, so that is the one to accept a finding with. In a merge commit gitleaks names
      # the file b/<path>; the path after a squash merge has no b/, so drop it for merges only (a
      # real top folder named b keeps its name).
      merges=$(git rev-list --min-parents=2 "$range" --)
      jq -r --arg merges "$merges" 'unique_by(.Fingerprint) | .[]
        | .Commit as $c
        | (if ($c != "" and ($merges | contains($c))) then (.File | sub("^b/"; "")) else .File end) as $f
        | "  \($f):\(.StartLine)  rule \(.RuleID)  commit \(.Commit[0:12])\n    to accept it, add this line to .gitleaksignore: \($f):\(.RuleID):\(.StartLine)"' "$tmp/report.json" >&2
      [ "$logged_err" = no ] || echo "secret-scan-ci: gitleaks also logged errors (the ERR lines above), so there may be more" >&2
      exit 1
    fi
  elif grep -q '"Fingerprint"' "$tmp/report.json"; then
    echo "secret-scan-ci: secrets found in '$range'; install jq to list them without the secret text (brew install jq)" >&2
    exit 1
  fi
fi

if [ "$logged_err" = yes ]; then
  echo "secret-scan-ci: gitleaks could not read all of '$range' (the ERR lines above), so the scan did not finish. Run git fetch, pass a BASE this checkout has, or update git (2.36 or later)." >&2
  exit 2
fi
if [ "$status" -ne 0 ]; then
  echo "secret-scan-ci: gitleaks stopped with exit $status (see its log above)" >&2
  exit 2
fi

echo "secret-scan-ci: no secrets in the $commits commit(s) of '$range'"

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
# For such a finding the scan suggests two .gitleaksignore lines, one for each form of the name.
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
# - A .gitleaksignore line in the form the scan suggests (file:rule:line, no commit id) names no
#   commit, so a squash merge does not break it, but the line number must still match. The scan
#   names a second line when a later commit on the branch moved the secret. If main adds lines
#   above it before the merge, the run on main names a new line, and that is fixed by hand.
#   Such a line also accepts any later secret the same rule finds on that line of that file.
#   That is why .gitleaksignore needs a person's sign-off.
# - On the Mac, a setting kept inside one checkout can still hide a secret: a line like `* -diff`
#   in its .git/info/attributes, or a setting in its .git/config that the scan does not pin.
#   GitHub's fresh checkout has neither, so its check is the safety net for those.
#
# Exit status: 0 nothing found, 1 secrets found, 2 the scan could not run, did not finish, or had
# no commits to scan.
set -u

PINNED=8.30.1   # the version the GitHub check installs; keep it the same as the workflow's

# Every git call below, gitleaks' own included, reads the real commits with no personal or system
# config (~/.gitconfig, ~/.config/git/config, /etc/gitconfig), no settings passed in the
# environment (git -c, GIT_CONFIG_PARAMETERS), and no local stand-in commits (git replace). Any of
# those could make the scan read something other than the real diff and pass with a secret in it.
# Settings are switched off as a whole, not one by one, so a new one can't slip through.
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_NOSYSTEM=1
GIT_NO_REPLACE_OBJECTS=1
export GIT_CONFIG_GLOBAL GIT_CONFIG_NOSYSTEM GIT_NO_REPLACE_OBJECTS
unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT

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
# Personal and system config are already off (see the top). The settings below also win over the
# checkout's own .git/config, for the ones that matter most: colour codes or a file named i/<path>
# instead of b/<path> could make gitleaks find nothing, log.showRoot=false would hide the first
# commit's diff, and log.abbrevCommit would shorten the commit ids the findings below are matched
# by. core.attributesFile=/dev/null and --no-textconv stop a personal attributes file
# (~/.config/git/attributes) marking files binary (-diff) or passing them through a filter. The
# repo's own .gitattributes still applies, as it does on GitHub. The trailing -- keeps a file
# named like the range (HEAD) from being read as a path.
GIT_CONFIG_COUNT=9 \
  GIT_CONFIG_KEY_0=color.ui GIT_CONFIG_VALUE_0=never \
  GIT_CONFIG_KEY_1=color.diff GIT_CONFIG_VALUE_1=never \
  GIT_CONFIG_KEY_2=diff.noprefix GIT_CONFIG_VALUE_2=false \
  GIT_CONFIG_KEY_3=diff.mnemonicPrefix GIT_CONFIG_VALUE_3=false \
  GIT_CONFIG_KEY_4=diff.srcPrefix GIT_CONFIG_VALUE_4=a/ \
  GIT_CONFIG_KEY_5=diff.dstPrefix GIT_CONFIG_VALUE_5=b/ \
  GIT_CONFIG_KEY_6=log.showRoot GIT_CONFIG_VALUE_6=true \
  GIT_CONFIG_KEY_7=log.abbrevCommit GIT_CONFIG_VALUE_7=false \
  GIT_CONFIG_KEY_8=core.attributesFile GIT_CONFIG_VALUE_8=/dev/null \
  gitleaks git --no-banner --redact --report-format json --report-path "$tmp/report.json" \
  --log-opts="--no-textconv --diff-merges=remerge $range --" . 2>"$tmp/log"
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
      # new commit, so that is the one to accept a finding with. Extra lines are named when the
      # branch's own check and the check on main after a squash merge need different ones.
      merges=$(git rev-list --min-parents=2 "$range" --)
      jq -r 'unique_by(.Fingerprint) | .[] | [.File, (.StartLine | tostring), .RuleID, .Commit] | @tsv' \
        "$tmp/report.json" >"$tmp/findings.tsv"
      tab=$(printf '\t')
      while IFS=$tab read -r file line rule commit; do
        # In a merge commit gitleaks names the file b/<path>, and a squash merge names it <path>.
        # Only merge commits lose the b/, so a real top folder named b keeps its name.
        path=$file
        if [ -n "$commit" ]; then
          case $merges in *"$commit"*) path=${file#b/} ;; esac
        fi
        echo "  $path:$line  rule $rule  commit $(printf '%.12s' "$commit")" >&2
        echo "    to accept it, add this line to .gitleaksignore: $path:$rule:$line" >&2
        if [ "$path" != "$file" ]; then
          echo "    and, for this branch's own check (a merge commit names the file b/<path>): $file:$rule:$line" >&2
        fi
        # A squash merge puts the line where it is now. If a later commit on the branch moved it,
        # name that line too. Best effort: when git can't place it, nothing extra is printed.
        now=$(git blame --porcelain HEAD -- "$path" 2>/dev/null \
          | awk -v c="$commit" -v n="$line" '$1 == c && $2 == n { print $3; exit }')
        if [ -n "$now" ] && [ "$now" != "$line" ]; then
          echo "    and, for the check on main after a squash merge (a later commit moved the line): $path:$rule:$now" >&2
        fi
      done <"$tmp/findings.tsv"
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

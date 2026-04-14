# /release

Cut a new release of the `earlbear/tap` Homebrew tap, and optionally update the
`earlbear-installer` cask when `EarlBear/apps` has shipped a new installer DMG.

## Usage

```
/release [VERSION]
/release --check        # just audit what needs releasing, no changes
/release --installer    # only update the installer cask (no tap release)
```

If VERSION is omitted, ask the user for it (e.g. `1.0.1`).

---

## Pre-flight: detect what actually needs releasing

Before doing anything, run this audit so you know what's changed:

```bash
# 1. What changed in sibling repos since the last tap tag?
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "none")
echo "Last tap tag: $LAST_TAG"

git -C ../earlbear-clis        log --oneline $(git ls-remote ../earlbear-clis HEAD | cut -f1)..HEAD -- 2>/dev/null | head -10 || true
git -C ../earlbear              log --oneline HEAD~5..HEAD -- bin/agent-cli 2>/dev/null | head -5 || true
git -C ../earlbear-claude-plugin-marketplace log --oneline HEAD~5..HEAD 2>/dev/null | head -5 || true

# 2. Has EarlBear/apps shipped a new installer release?
LATEST_INSTALLER=$(gh release list --repo EarlBear/apps --limit 1 --json tagName,createdAt \
  --jq '.[0] | "\(.tagName)  \(.createdAt)"' 2>/dev/null || echo "unknown")
CASK_VERSION=$(grep '^  version' Casks/earlbear-installer.rb | awk -F'"' '{print $2}')
echo "Latest EarlBear/apps release: $LATEST_INSTALLER"
echo "Cask currently pinned to:     installer-v$CASK_VERSION"
```

Use this output to decide:
- Sibling repos have new commits → tap release needed
- `EarlBear/apps` tag is newer than the cask version → installer cask update needed
- Neither → nothing to do; confirm with user before aborting

---

## Path A: Tap release (Formula/*.rb)

### A1. Sync sources

```bash
make sync-sources
git diff src/ plugins-bundle/   # review what changed
```

If nothing changed in `src/`, confirm with user — the source repos may not have been updated.

### A2. Validate

```bash
make validate-audit    # ~30s — Ruby syntax + Homebrew policy
make validate-docker   # ~5min — full brew install in Docker
```

Fix any failures before proceeding. Do NOT release a broken tap.

### A3. Tag and push

```bash
git add -A
git commit -m "chore: sync sources + bump to vVERSION"
make bump-and-release VERSION=<VERSION>
```

`bump-and-release` creates an annotated tag, pushes it, creates a GitHub Release,
and uploads plugin binaries.

### A4. Patch formula sha256

Wait ~30s for the GitHub tarball to be available, then:

```bash
curl -sL https://github.com/EarlBear/homebrew-tap/archive/refs/tags/vVERSION.tar.gz \
  -o /tmp/tap-vVERSION.tar.gz
NEW_SHA=$(shasum -a 256 /tmp/tap-vVERSION.tar.gz | awk '{print $1}')
echo "sha256: $NEW_SHA"
```

Update **every** `Formula/*.rb` (all 7 share the same tarball url+sha256):
- `url`: replace old version tag → new
- `sha256` (first one, not resource sha256s): replace old hash → new

```bash
OLD_TAG="v1.0.0"   # previous tag
NEW_TAG="vVERSION"

for f in Formula/*.rb; do
  sed -i '' \
    "s|homebrew-tap/archive/refs/tags/${OLD_TAG}.tar.gz|homebrew-tap/archive/refs/tags/${NEW_TAG}.tar.gz|g" \
    "$f"
  # Replace the top-level sha256 (first occurrence only — not resource sha256s)
  awk -v old="$OLD_SHA" -v new="$NEW_SHA" \
    'NR==1,/sha256 "'"$OLD_SHA"'"/{sub(/sha256 "'"$OLD_SHA"'"/, "sha256 \"" new "\"")} {print}' \
    "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

git add Formula/
git commit -m "fix: update formula url+sha256 to vVERSION"
git push
```

> **Tip:** Verify with `grep -h "sha256\|url" Formula/*.rb | head -16` — all 7 should have the same new hash.

---

## Path B: Installer cask update (Casks/earlbear-installer.rb)

Run this whenever `EarlBear/apps` has a new `installer-vX.Y.Z` release.

### B1. Find the new release

```bash
gh release view --repo EarlBear/apps installer-vNEW_VERSION --json assets \
  --jq '.assets[] | select(.name | endswith(".dmg")) | .browserDownloadUrl'
```

### B2. Download and compute sha256

```bash
NEW_INSTALLER_VERSION="1.0.1"   # the new version
DMG_URL="https://github.com/EarlBear/apps/releases/download/installer-v${NEW_INSTALLER_VERSION}/EarlBear-Installer-${NEW_INSTALLER_VERSION}.dmg"

curl -sL "$DMG_URL" -o "/tmp/EarlBear-Installer-${NEW_INSTALLER_VERSION}.dmg"
NEW_SHA=$(shasum -a 256 "/tmp/EarlBear-Installer-${NEW_INSTALLER_VERSION}.dmg" | awk '{print $1}')
echo "sha256: $NEW_SHA"
```

### B3. Patch the cask

Update `Casks/earlbear-installer.rb`:
- `version`: new version string
- `sha256`: new hash

```bash
git add Casks/earlbear-installer.rb
git commit -m "chore: update earlbear-installer cask to v${NEW_INSTALLER_VERSION}"
git push
```

---

## Path C: Both (tap release + installer cask update)

Do Path A first (tap gets a new tag), then Path B (installer cask), combining into one push:

```bash
git add Formula/ Casks/earlbear-installer.rb
git commit -m "fix: bump tap to vVERSION, installer cask to vINSTALLER_VERSION"
git push
```

---

## Release checklist

- [ ] Pre-flight audit run — know what's actually changing
- [ ] `make validate-audit` green
- [ ] `make validate-docker` green (Path A only)
- [ ] Formula sha256 patched with real tarball hash (Path A)
- [ ] Cask sha256 downloaded from actual DMG (Path B)
- [ ] `grep -h "sha256\|url" Formula/*.rb | head -16` — all 7 formulas have same hash
- [ ] `grep sha256 Casks/earlbear-installer.rb` — cask hash matches DMG download
- [ ] Pushed and `brew update && brew upgrade earlbear/tap/ebdeck` works (spot check)

## Notes

- The Docker Dockerfile patches sha256 at build time, so `validate-docker` passes even
  with stale hashes. Always patch the real sha256 before tagging.
- Formula sha256s all point to the same tap tarball — one `curl` + one hash, applied to
  all 7 `Formula/*.rb`. Resource sha256s (inside `ebdeck.rb`) are PyPI hashes and
  never change on a tap release.
- The cask (`Casks/earlbear-installer.rb`) points to the `EarlBear/apps` DMG — a
  completely separate hash from the tap tarball.
- Installer releases in `EarlBear/apps` are tagged `installer-vX.Y.Z` (not `vX.Y.Z`).
  The tap's own releases are tagged `vX.Y.Z`. These are independent and can move at
  different cadences.
- If releasing a new formula, run `/add-formula` first and get it Docker-validated
  before including in a tap release.

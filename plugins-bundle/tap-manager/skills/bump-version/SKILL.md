# /bump-version

Bump the version of one or more earlbear-homebrew formulas to a new release.

## Usage

```
/bump-version VERSION=1.0.2
/bump-version FORMULA=ebdeck VERSION=1.0.2
```

## Steps

### 1. Sync latest sources
```bash
cd ~/Workspace/git/earlbear-homebrew
make sync-sources
```

### 2. Create the release tarball (after pushing to GitHub)
Once the new tag exists at `github.com/EarlBear/homebrew-tap`:
```bash
NEW_VERSION=1.0.2
URL="https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v${NEW_VERSION}.tar.gz"
curl -L "$URL" -o /tmp/tap-v${NEW_VERSION}.tar.gz
SHA=$(sha256sum /tmp/tap-v${NEW_VERSION}.tar.gz | awk '{print $1}')
echo "sha256: $SHA"
```

### 3. Update all formulas
For each `Formula/*.rb`:
- Update `url` to use the new tag: `v${NEW_VERSION}`
- Update `sha256` to `$SHA`

### 4. Update Python resource sha256s (ebdeck only)
```bash
brew update-python-resources earlbear/tap/ebdeck
```
This auto-updates all `resource` sha256s in `Formula/ebdeck.rb`.

### 5. Run Tier 1 validation
```bash
brew style Formula/*.rb
brew audit --skip-style earlbear/tap/ebjira [...]
```

### 6. Commit + tag + push
```bash
git add Formula/
git commit -m "chore: bump all formulas to v${NEW_VERSION}"
make bump-and-release VERSION=${NEW_VERSION}
```

### 7. Run Tier 2 validation (Docker)
```bash
make validate-docker
```

## Notes

- `sha256 "000...0"` is the placeholder for unreleased versions (before pushing to GitHub)
- The Docker validation Dockerfile patches URLs to use a local archive, so Tier 2 works before GitHub release
- For Python resource updates, `brew update-python-resources` requires the formula to be tapped

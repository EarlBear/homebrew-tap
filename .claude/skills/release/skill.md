# /release

Cut a new release of the `earlbear/tap` Homebrew tap.

## Usage

```
/release [VERSION]
```

If VERSION is omitted, ask the user for it (e.g. `1.0.1`).

## Steps

### 1. Sync sources from sibling repos

```bash
make sync-sources
```

This pulls the latest CLI source into `src/` from:
- `../earlbear-clis/jira-cli/` → `src/ebjira/`
- `../earlbear-clis/gdocs-cli/` → `src/ebdocs/`
- `../earlbear-clis/shopify-cli/` → `src/ebshop/`
- `../earlbear-clis/deck-cli/` → `src/ebdeck/`
- `../earlbear/bin/agent-cli` → `src/agent-cli/`
- `../earlbear-claude-plugin-marketplace/plugins/` → `plugins-bundle/`

Check `git diff src/` to see what changed. If nothing changed, the source repos haven't been updated — confirm with user before proceeding.

### 2. Run validation suite

```bash
make validate-audit    # ~30s
make validate-docker   # ~5min — most important
```

Fix any failures before proceeding. Do NOT release a broken tap.

### 3. Tag and push

```bash
git add -A
git commit -m "chore: sync sources + bump to vVERSION"
make bump-and-release VERSION=<VERSION>
```

`bump-and-release` will `git tag -a vVERSION` and `git push origin main vVERSION`.

### 4. Compute new sha256 and patch formulas

After the GitHub release tarball is live (~30s after tag push):

```bash
curl -sL https://github.com/EarlBear/homebrew-tap/archive/refs/tags/vVERSION.tar.gz \
  -o /tmp/vVERSION.tar.gz
shasum -a 256 /tmp/vVERSION.tar.gz
```

Update in every `Formula/*.rb`:
- `url` line: replace old version tag with new
- `sha256` line: replace old hash with new

```bash
git add Formula/
git commit -m "fix: update formula url+sha256 to vVERSION"
git push
```

### 5. Verify

```bash
brew update
brew upgrade earlbear/tap/ebdeck  # spot check one formula
```

## Notes

- The Docker Dockerfile patches the sha256 at build time, so `validate-docker` passes even with placeholder hashes. Always patch the real sha256 before tagging so real users don't hit a checksum mismatch.
- If releasing a new formula, run `/add-formula` first and get it Docker-validated before including in the release.

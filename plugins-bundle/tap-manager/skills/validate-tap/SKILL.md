# /validate-tap

Run the earlbear-homebrew validation suite and report failures.

## Steps

1. **Read current state**
   ```bash
   cd ~/Workspace/git/earlbear-homebrew
   git status
   ls Formula/
   ```

2. **Tier 1 — brew style + audit (local, ~10s)**
   ```bash
   brew style Formula/*.rb
   brew audit --skip-style earlbear/tap/ebjira \
     earlbear/tap/ebdocs earlbear/tap/ebshop \
     earlbear/tap/ebdeck earlbear/tap/agent-cli \
     earlbear/tap/earlbear-plugins earlbear/tap/earlbear
   ```
   If the tap isn't tapped locally: `brew tap earlbear/tap "file://$(pwd)"`

3. **Tier 2 — Docker install (~5min)**
   ```bash
   make validate-docker
   ```
   This builds `validation/docker/Dockerfile` which patches formula URLs to use a local
   archive, then runs `brew install --build-from-source` for ebdeck and earlbear-plugins.

4. **Tier 4 — Smoke test (~10s, Mac only)**
   ```bash
   make validate-smoke
   ```
   Only run if the formulas are locally installed.

5. **Tier 3 — Tart VM (~15min, optional)**
   ```bash
   make validate-vm
   ```
   Full clean-room macOS VM test. Requires `tart` installed and Apple Silicon.

## How to handle failures

- **`brew style` offense**: fix the ruby style (rubocop), re-run
- **`brew audit` problem**: usually version/url/desc/dependency issue — fix formula, re-run  
- **Docker install failure**: check if `src/` files are present and correct, check formula `install` block
- **ebdeck `--help` fails**: Python venv build failed — check resource sha256s, try `brew update-python-resources ebdeck`
- **Smoke test failure**: check wrapper scripts in `src/*/wrapper.sh`

## Output

Report: tier, pass/fail, any error output. Use `- [ ]` for failures, `- [x]` for passes.

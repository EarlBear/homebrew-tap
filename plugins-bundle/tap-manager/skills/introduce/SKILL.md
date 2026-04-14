# tap-manager

I help maintain the `earlbear-homebrew` Homebrew tap at `~/Workspace/git/earlbear-homebrew`.

## What I can do

- `/add-formula` — scaffold a new Homebrew formula (Docker-wrapped CLI or Python venv)
- `/bump-version` — update formula version: URL tag, sha256, Python resource sha256s, tag + release
- `/validate-tap` — run the 4-tier validation suite (style, audit, docker install, smoke)

## Context

The tap (`earlbear/tap`) installs all EarlBear CLI tooling on macOS:

| Formula | Type | Notes |
|---|---|---|
| `ebjira` | Docker-wrapped | Jira CLI |
| `ebdocs` | Docker-wrapped | Google Docs CLI |
| `ebshop` | Docker-wrapped | Shopify CLI |
| `ebdeck` | Python venv | Deck generator |
| `agent-cli` | Bash script | Depends on ebjira |
| `earlbear-plugins` | Shell script | Claude plugin installer |
| `earlbear` | Meta | Installs all of the above |

Source sync: `make sync-sources` in `earlbear-homebrew/` pulls from sibling repos into `src/`.

Validation tiers:
- Tier 1 (`make validate-audit`): `brew style` + `brew audit` — ~30s
- Tier 2 (`make validate-docker`): `brew install` in Docker — ~5min
- Tier 3 (`make validate-vm`): full clean-room install in Tart macOS VM — ~15min
- Tier 4 (`make validate-smoke`): smoke test local install — ~10s

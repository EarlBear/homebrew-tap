# EarlBear Secrets Architecture — Plan

## Context

The question: should secrets move from a plaintext `.env` file to a dedicated secrets CLI that other CLIs call at runtime? The `.env` approach is working but feels like a security gap — `cat ~/.config/earlbear/.env` exposes everything at once, and `agent-cli.sh` sources the whole file into the shell environment.

After analyzing the actual threat model and the Docker container constraint (ebjira, ebdocs, ebshop run inside Docker and can't call a host CLI), the answer is: **don't build a secrets CLI**. The Docker wall makes it impossible to consolidate retrieval — you'd always need two paths. Instead, use macOS Keychain as the primary at-rest store for sensitive tokens, keep `.env` for non-secret config and Docker injection, and fix the one real leak (agent-cli sourcing the full env file).

---

## Security Analysis

| Threat | Current `.env` 0o600 | After this plan |
|--------|----------------------|-----------------|
| `cat .env` exposes tokens | Yes — all tokens in one readable file | Tokens in Keychain, not in `.env` |
| `ps aux` leakage | Low (Docker uses `--env-file` API, not args) | Same |
| `agent-cli` sources full env into shell | Yes — all vars exported | Fixed — only needed vars fetched individually |
| Log leakage | Guarded at CLI level (redaction patterns exist) | Same |
| Audit trail | None | None (acceptable at current team size) |

**Why not a secrets CLI:** Docker containers (ebjira, ebdocs, ebshop) can't exec a host-side binary. Any secrets CLI would still need to generate an env-file for Docker, so the `.env` file doesn't go away — it just has another layer on top. Net result: more complexity, same security posture for 3 of 5 CLIs.

**When to revisit:** Team grows to 5+ devs, or a CI/cron use case emerges where unattended secret rotation matters. At that point, 1Password CLI (op run) or AWS Secrets Manager is the right answer, not a home-built CLI.

---

## Recommendation: Keychain-first, `.env` for Docker

Two targeted changes. Everything else stays the same.

### Change 1 — Installer writes sensitive keys to macOS Keychain

**File:** `installer/gui/app.py` — `run_step_8_credentials()` (around line 722)

After successfully writing the decrypted blob to `~/.config/earlbear/.env`, iterate over the sensitive keys and write each to Keychain using the macOS `security` CLI:

```python
KEYCHAIN_KEYS = [
    "JIRA_API_TOKEN",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REFRESH_TOKEN",
    "SHOPIFY_ACCESS_TOKEN",
    "SUPABASE_SERVICE_ROLE_KEY",
]

def _write_to_keychain(key: str, value: str):
    subprocess.run([
        "security", "add-generic-password",
        "-U",                       # update if exists
        "-a", os.environ.get("USER", "earlbear"),
        "-s", f"earlbear.{key}",
        "-w", value,
    ], capture_output=True)
```

Parse the decrypted `.env` bytes into a dict (simple `KEY=VALUE` split), then call `_write_to_keychain` for each key in `KEYCHAIN_KEYS` that is present. Non-secret config (`JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_PROJECT`, `GOOGLE_DRIVE_FOLDER_ID`, `SHOPIFY_STORE_URL`) stays only in `.env`.

The `.env` file write is **kept as-is** — Docker CLIs still need it. Keychain is additive.

The pre-check for step 8 (`~/.config/earlbear/.env` exists) is unchanged.

### Change 2 — `agent-cli.sh` reads tokens from Keychain, not `source`

**File:** `src/agent-cli/agent-cli.sh` (line 26 currently does `source "$ENV_FILE"`)

Replace the `source` with per-key reads. Non-secret config still comes from `.env` via `grep`:

```bash
# Non-secret config from .env (safe to grep, these aren't tokens)
JIRA_BASE_URL="$(grep -s '^JIRA_BASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
JIRA_USER_EMAIL="$(grep -s '^JIRA_USER_EMAIL=' "$ENV_FILE" | cut -d= -f2-)"
JIRA_PROJECT="${JIRA_PROJECT:-$(grep -s '^JIRA_PROJECT=' "$ENV_FILE" | cut -d= -f2-)}"
JIRA_PROJECT="${JIRA_PROJECT:-EARL}"

# Sensitive tokens from Keychain, with fallback to .env for older installs
_keychain_get() {
  security find-generic-password -a "$USER" -s "earlbear.$1" -w 2>/dev/null \
    || grep -s "^$1=" "$ENV_FILE" | cut -d= -f2-
}
JIRA_API_TOKEN="$(_keychain_get JIRA_API_TOKEN)"

export JIRA_BASE_URL JIRA_USER_EMAIL JIRA_PROJECT JIRA_API_TOKEN
```

The Keychain fallback to `.env` is important: existing devs with older installs (no Keychain write) continue to work without re-running the installer.

Delete the `source "$ENV_FILE"` line entirely.

---

## What stays the same

- **Docker wrappers** (`wrappers/ebjira/`, `ebdocs/`, `ebshop/`): `--env-file` is already the correct approach for Docker and is not exposed in `ps aux`. No change.
- **Python CLI configs** (`src/ebjira/config.py`, etc.): read `os.environ` inside the container — Docker injects them cleanly. No change.
- **ebdeck**: reads no secrets directly. No change.
- **Gist distribution** (`scripts/export-creds.sh`): the encrypted blob + passphrase mechanism is correct. No change.
- **Installer GUI**: overall flow, pre-checks, step states — no change beyond the Keychain write in step 8.
- **Homebrew formulas**: no change.

---

## Change 3 — Makefile targets for Keychain ↔ `.env` lifecycle

**File:** `earlbear-apps/Makefile`

Four new targets covering the full secrets lifecycle:

```makefile
# ── Secrets / Keychain ────────────────────────────────────────────────────────

keychain-status: ## Show which earlbear secrets are in Keychain (SET/MISSING)
	@bash scripts/keychain-secrets.sh status

keychain-to-env: ## Regenerate ~/.config/earlbear/.env from Keychain entries
	@bash scripts/keychain-secrets.sh to-env

env-to-keychain: ## Write sensitive keys from ~/.config/earlbear/.env into Keychain
	@bash scripts/keychain-secrets.sh from-env

keychain-set: ## Set a single secret: make keychain-set KEY=JIRA_API_TOKEN VALUE=xxx
	@bash scripts/keychain-secrets.sh set "$(KEY)" "$(VALUE)"
```

**New script: `scripts/keychain-secrets.sh`**

Single script, four subcommands:

- **`status`** — loops over `KEYCHAIN_KEYS`, prints `SET` or `MISSING` per key. No values printed.
- **`to-env`** — reads each key from Keychain via `security find-generic-password -w`, reads non-secret config from existing `.env`, merges, writes a fresh `~/.config/earlbear/.env` with `chmod 600`. Lets a dev reconstitute `.env` on a machine that already has Keychain populated (e.g. after deleting `.env` or migrating to a new shell).
- **`from-env`** — reads `~/.config/earlbear/.env`, writes sensitive keys to Keychain via `security add-generic-password -U`. Same logic as the installer step 8 Keychain write, but callable from the terminal without re-running the GUI. Useful for devs who set up `.env` manually.
- **`set KEY VALUE`** — writes a single key to Keychain and updates `.env` in place (replaces the line). Covers individual secret rotation without re-running the full installer.

`KEYCHAIN_KEYS` list (sensitive tokens only — not URLs, emails, project keys):
```bash
KEYCHAIN_KEYS=(
  JIRA_API_TOKEN
  GOOGLE_OAUTH_CLIENT_SECRET
  GOOGLE_OAUTH_REFRESH_TOKEN
  SHOPIFY_ACCESS_TOKEN
  SUPABASE_SERVICE_ROLE_KEY
)
```

Non-secret config keys (`JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_PROJECT`, `GOOGLE_DRIVE_FOLDER_ID`, `SHOPIFY_STORE_URL`, `GOOGLE_OAUTH_CLIENT_ID`) live only in `.env` — not in Keychain. They're not sensitive enough to warrant Keychain storage.

---

## Critical Files

| File | Change |
|------|--------|
| `installer/gui/app.py` | Add Keychain write in `run_step_8_credentials()` after `.env` write |
| `src/agent-cli/agent-cli.sh` | Replace `source "$ENV_FILE"` with per-key grep + Keychain reads |
| `Makefile` (earlbear-apps) | Add 4 keychain-* targets |
| `scripts/keychain-secrets.sh` | New script — status / to-env / from-env / set subcommands |

---

## Dev Workflow After This Change

```
New dev (via installer):
  Step 8 GUI → decrypt blob → writes .env + Keychain entries

New dev (manual, no GUI):
  Put real values in ~/.config/earlbear/.env
  make env-to-keychain       ← writes sensitive keys to Keychain

Check what's set:
  make keychain-status

Rotate one secret:
  make keychain-set KEY=JIRA_API_TOKEN VALUE=new-token

Rebuild .env from scratch (e.g. after rm .env):
  make keychain-to-env

Team lead rotates all secrets:
  Edit ~/.config/earlbear/.env
  make env-to-keychain       ← updates Keychain
  make export-creds          ← re-encrypts and pushes new Gist blob
```

---

## Verification

```bash
# 1. Run installer step 8 → confirm both .env and Keychain populated
make dev
# Complete step 8 in GUI
security find-generic-password -a "$USER" -s "earlbear.JIRA_API_TOKEN" -w
make keychain-status

# 2. Test to-env round-trip
rm ~/.config/earlbear/.env
make keychain-to-env
cat ~/.config/earlbear/.env   # should have all keys

# 3. Test from-env (manual setup path)
security delete-generic-password -a "$USER" -s "earlbear.JIRA_API_TOKEN" 2>/dev/null || true
make env-to-keychain
security find-generic-password -a "$USER" -s "earlbear.JIRA_API_TOKEN" -w

# 4. Test agent-cli Keychain fallback
mv ~/.config/earlbear/.env ~/.config/earlbear/.env.bak
agent-cli checkin   # reads JIRA_API_TOKEN from Keychain
mv ~/.config/earlbear/.env.bak ~/.config/earlbear/.env
```

---

## Effort

~1.5 days total: installer Keychain write (2h), agent-cli fix (1h), keychain-secrets.sh script (2h), Makefile targets (30m), testing (3h).

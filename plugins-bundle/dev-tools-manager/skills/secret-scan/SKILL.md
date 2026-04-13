---
name: secret-scan
description: Scan the repository for leaked secrets using gitleaks. Installs gitleaks if missing, configures git hooks if they don't exist, and ensures CLAUDE.md and memory are up to date so scans run automatically on every commit and push.
allowed-tools: Bash(gitleaks *), Bash(which *), Bash(brew *), Bash(chmod *), Bash(make secret-scan*), Read, Edit, Write, Grep, Glob
---

# Secret Scan

Scan the repository for leaked secrets and ensure the scan is wired into every part of the development workflow.

## Step 1: Install gitleaks if missing

```bash
which gitleaks || brew install gitleaks
```

## Step 2: Run the scan

**Staged changes (pre-commit style):**
```bash
gitleaks protect --staged --verbose
```

**Full repo scan:**
```bash
gitleaks detect --source . --verbose
```

**Via Makefile:**
```bash
make secret-scan
```

## Step 3: Configure git hooks if they don't exist

Check what exists:
```bash
ls -la .git/hooks/pre-commit .git/hooks/pre-push 2>/dev/null
```

**If hooks already exist:** read them first — append gitleaks commands only if not already present.

**If using a hook manager** (husky, lefthook, pre-commit framework): integrate through that tool's config instead.

**If no hooks exist, create them:**

`.git/hooks/pre-commit`:
```bash
#!/bin/sh
if ! command -v gitleaks &> /dev/null; then
    echo ""
    echo "ERROR: gitleaks is not installed."
    echo "Install it with: brew install gitleaks"
    echo ""
    echo "Commits are blocked until gitleaks is available."
    echo "This is required to prevent secrets from being committed."
    exit 1
fi
echo "Scanning staged changes for secrets..."
gitleaks protect --staged --verbose
```

`.git/hooks/pre-push` (secret scan + tests):
```bash
#!/bin/sh

# === Secret scan ===
if ! command -v gitleaks &> /dev/null; then
    echo ""
    echo "ERROR: gitleaks is not installed."
    echo "Install it with: brew install gitleaks"
    echo ""
    echo "Pushes are blocked until gitleaks is available."
    exit 1
fi
echo "Running full secret scan before push..."
gitleaks detect --source . --verbose
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Secret scan failed. Push blocked."
    exit 1
fi

# === Tests ===
echo ""
echo "Running tests before push..."
make all-test    # Adjust per repo: make test, make sim-test, etc.
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Tests failed. Push blocked."
    echo "Fix failing tests and try again."
    exit 1
fi
echo "Tests passed."
```

Make both executable: `chmod +x .git/hooks/pre-commit .git/hooks/pre-push`

### What each hook enforces

| Hook | Checks | Blocks on |
|------|--------|-----------|
| **pre-commit** | gitleaks staged scan | Missing gitleaks, leaked secrets |
| **pre-push** | gitleaks full scan + `make *-test` | Missing gitleaks, leaked secrets, failing tests |

### Test targets per repo

| Repo | pre-push test command | What it runs |
|------|----------------------|-------------|
| earlbear-clis | `make all-test` | ebshop (419), ebjira (361), ebdocs (134) tests |
| earlbear-shopify-app-cli | `make test` | ESLint + production build |
| earlbear-claude-agent | `make sim-test` | 7 proxy simulation tests |
| earlbear (monorepo) | gitleaks only | CLI tests run via earlbear-clis |

Hooks **block** commits and pushes if gitleaks is not installed or tests fail. No exceptions.

## Step 4: Verify CLAUDE.md has security guidance

Read `CLAUDE.md` and confirm it contains guidance about running secret scans before commits. If the security section is missing or incomplete, add:

```markdown
## Security
- Always run `make secret-scan` before committing or pushing.
- Git hooks automate this, but verify they are configured.
- Never hardcode secrets — use `.env` files (gitignored).
- See `.claude/skills/secret-scan/SKILL.md` for setup details.
```

## Step 5: Verify memory if Claude won't auto-invoke

If git hooks aren't in place (e.g., fresh clone where `.git/hooks/` is empty), save a feedback memory so future sessions know to run the scan and reconfigure hooks:

> Always run `make secret-scan` before committing in this repo. On fresh clones, run `/secret-scan` to reinstall hooks since `.git/hooks/` is not tracked by git.

## What it checks
- API keys and secrets
- Tokens (access, refresh, JWT)
- Passwords and credentials
- Private keys
- Connection strings
- Default gitleaks ruleset patterns

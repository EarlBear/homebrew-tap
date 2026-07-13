#!/usr/bin/env sh
# repo-setup-guard — a SessionStart guard that makes sure THIS repo is safely configured for
# work before the session begins. It closes a real drift: git's core.hooksPath is per-CLONE
# LOCAL config (not committed), so a fresh clone has NO active hooks until someone remembers to
# run `make install-hooks`. A committed pre-commit secret scanner is worthless if it isn't wired.
# This runs on every SessionStart and heals that automatically.
#
# Split of responsibility (decided with the user):
#   AUTO-HEAL (safe, mechanical, idempotent):
#     - if a committed .githooks/pre-commit exists but core.hooksPath is unset → wire it.
#   WARN ONLY (needs a human / a decision — never block, never install software):
#     - gitleaks not on PATH → the secret scan can't run; nudge `brew install gitleaks`.
#     - core.hooksPath points at a dir with no pre-commit → the wiring is half-done.
#     - a tracked .env* holds a plaintext value (repo has the dotenvx check) → nudge encrypt.
#
# NEVER blocks the session (always exits 0) and is a NO-OP when the repo is already correct —
# so it's quiet in the common case and only speaks when something needs attention.
#
# Invoked from .claude/settings.json SessionStart. Portable POSIX sh, no Python required.
set -u

# Only meaningful inside a git work tree.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$ROOT" || exit 0

notes=""      # accumulated advisory lines (printed once at the end)
healed=""     # accumulated auto-heal lines

have_gitleaks() { command -v gitleaks >/dev/null 2>&1; }

# ---- 1. AUTO-HEAL: wire core.hooksPath if a committed hook dir exists but isn't active -------
current_hp=$(git config --local core.hooksPath 2>/dev/null || true)
if [ -f ".githooks/pre-commit" ]; then
  if [ -z "$current_hp" ]; then
    git config --local core.hooksPath .githooks 2>/dev/null \
      && healed="${healed}  ✓ wired core.hooksPath → .githooks (a committed pre-commit existed but wasn't active).\n"
    current_hp=".githooks"
  fi
  # Make sure the committed hook is executable (a fresh clone can drop the bit).
  [ -x ".githooks/pre-commit" ] || chmod +x ".githooks/pre-commit" 2>/dev/null || true
fi

# ---- 2. WARN: hooksPath is set but the pre-commit is missing there (half-wired) --------------
if [ -n "$current_hp" ] && [ ! -f "$current_hp/pre-commit" ]; then
  notes="${notes}  ⚠ core.hooksPath is '$current_hp' but no pre-commit hook lives there — the secret scan won't run. Add one (copy another repo's .githooks/pre-commit) or unset the path.\n"
fi

# ---- 3. WARN: a repo with NO committed hook and NO hooksPath — is a scan expected? -----------
# Only nudge when there's a signal the repo intends secret scanning (a .gitleaks.toml), to avoid
# noise on repos that legitimately have no hook (a static site, a sandbox).
if [ -z "$current_hp" ] && [ ! -f ".githooks/pre-commit" ] && [ -f ".gitleaks.toml" ]; then
  notes="${notes}  ⚠ this repo has a .gitleaks.toml (secret-scan config) but NO pre-commit hook wired — commits are not being scanned. Add a .githooks/pre-commit that runs 'gitleaks protect --staged' and set core.hooksPath.\n"
fi

# ---- 4. WARN: gitleaks not installed → the committed hook will fail closed on commit ---------
if { [ -f ".githooks/pre-commit" ] || [ -f ".gitleaks.toml" ]; } && ! have_gitleaks; then
  notes="${notes}  ⚠ gitleaks is not installed — the pre-commit secret scan can't run. Install it: brew install gitleaks\n"
fi

# ---- 5. WARN: a tracked .env* looks unencrypted (only if the repo ships the dotenvx guard) ---
if [ -f ".claude/hooks/check-env-encrypted.py" ] && command -v python3 >/dev/null 2>&1; then
  if ! python3 .claude/hooks/check-env-encrypted.py --check >/dev/null 2>&1; then
    notes="${notes}  ⚠ a tracked .env* file holds a plaintext value — run 'make encrypt' before committing (see check-env-encrypted).\n"
  fi
fi

# ---- Report (only if there's something to say) ----------------------------------------------
if [ -n "$healed" ] || [ -n "$notes" ]; then
  printf '\n\033[1m[repo-setup-guard]\033[0m %s\n' "$(basename "$ROOT")"
  [ -n "$healed" ] && printf "$healed"
  [ -n "$notes" ] && printf "$notes"
  printf '\n'
fi
exit 0

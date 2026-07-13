"""Idempotent upsert of the read-only-source deny rules into ~/.claude/settings.json.

The Drive-consolidation feature enforces two immutability invariants as Claude Code
permissions (not just convention): the raw transcripts under ~/.claude/projects/** and the
scrubbed Drive output under abacus/** must never be modified by Write/Edit. `deny` rules
override allow/additionalDirectories, so these hold even where the dirs are otherwise granted.

This module writes/merges those deny rules WITHOUT clobbering anything else in the file:
  - missing file            -> create { "permissions": { "deny": [ …rules… ] } }
  - file w/o permissions    -> add the permissions.deny block, keep every other key
  - file w/ existing deny   -> set-union our rules into it (no duplicates), keep the rest

Used by the setup-google-drive skill and exercised by the clean-setup harness against all three
cases. Stdlib-only; pure function core (`merge_deny_rules`) so it is trivially testable, plus a
thin `upsert_settings_file` that does the read-before-write / atomic-write.
"""

from __future__ import annotations

import json
from pathlib import Path

# The deny rules the Drive feature requires. Kept here as the single source of truth so the
# skill, the CLI, and the tests all reference the same list. `~` expands; `**` is recursive.
DENY_RULES = [
    "Edit(~/.claude/projects/**)",
    "Write(~/.claude/projects/**)",
    "Edit(~/Library/CloudStorage/GoogleDrive-*/Shared drives/agent-workspace/abacus/**)",
    "Write(~/Library/CloudStorage/GoogleDrive-*/Shared drives/agent-workspace/abacus/**)",
    # Advisory (string-pattern) Bash denies — defense-in-depth for the obvious cases. Not
    # airtight (a variable-indirected write can slip past); the Edit/Write denies above are the
    # airtight layer for Claude's built-in tools.
    "Bash(rm -rf ~/.claude/*)",
    "Bash(sed -i * ~/.claude/projects/**)",
    "Bash(tee ~/.claude/projects/**)",
]


def merge_deny_rules(settings: dict, rules: list[str] | None = None) -> tuple[dict, list[str]]:
    """Return (new_settings, added_rules). Pure: does not mutate `settings`, no duplicates.

    Preserves every existing key; only touches settings["permissions"]["deny"], appending any
    rule not already present (set-union, order-stable: existing first, then new).
    """
    rules = DENY_RULES if rules is None else rules
    # Deep-ish copy of the parts we touch (settings values are JSON, so this is enough).
    new = dict(settings)
    permissions = dict(new.get("permissions") or {})
    existing_deny = list(permissions.get("deny") or [])

    added: list[str] = []
    seen = set(existing_deny)
    merged = list(existing_deny)
    for rule in rules:
        if rule not in seen:
            merged.append(rule)
            seen.add(rule)
            added.append(rule)

    permissions["deny"] = merged
    new["permissions"] = permissions
    return new, added


def upsert_settings_file(path: str | Path, rules: list[str] | None = None) -> list[str]:
    """Read-before-write upsert of the deny rules into the settings.json at `path`.

    Creates the file (and parent dir) if missing. Returns the list of rules actually added (empty
    if everything was already present — i.e. idempotent no-op on re-run). Raises ValueError if the
    existing file is present but not valid JSON (we refuse to clobber an unparseable file).
    """
    p = Path(path).expanduser()
    if p.exists():
        text = p.read_text()
        try:
            settings = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as e:
            raise ValueError(f"{p} is not valid JSON; refusing to overwrite: {e}") from e
        if not isinstance(settings, dict):
            raise ValueError(f"{p} top-level JSON is not an object; refusing to overwrite.")
    else:
        settings = {}

    new_settings, added = merge_deny_rules(settings, rules)
    if not added and p.exists():
        return []  # idempotent: nothing to write.

    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp then replace, so a crash never leaves a half-written settings file.
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(new_settings, indent=2) + "\n")
    tmp.replace(p)
    return added

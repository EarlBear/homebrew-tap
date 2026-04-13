#!/usr/bin/env python3
"""Stop-hook: remind Claude to verify living artifacts after file edits.

Fires at end of every turn via .claude/settings.json hooks.Stop. Reads
.claude/hooks/living-artifacts.yaml (sibling file), walks the git diff against
HEAD plus untracked files, matches changed paths against trigger globs, and
emits a markdown reminder block to stdout. Claude Code appends stdout from a
Stop hook to the conversation as additional context — so the reminder shows
up in Claude's next turn without blocking the stop.

Design:
- If nothing triggered, exit 0 silently (no noise on irrelevant turns).
- Never block the Stop flow: missing yaml, missing pyyaml, git errors — all
  degrade to a one-line stderr warning + exit 0.
- Dedupe reminders by exact string, collecting the matched files per reminder.

Config schema (living-artifacts.yaml):

    triggers:
      - when_changed: <glob, relative to repo root>
        remind:
          - <reminder string>
          - <reminder string>
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
CONFIG_FILE = HOOK_DIR / "living-artifacts.yaml"


def warn(msg: str) -> None:
    """Non-blocking warning. Goes to stderr, never breaks the Stop flow."""
    print(f"[check-living-artifacts] {msg}", file=sys.stderr)


def project_root() -> Path:
    """Resolve the project root. Prefer CLAUDE_PROJECT_DIR when set by Claude
    Code, fall back to walking up from the hook file."""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root).resolve()
    # Fallback: .claude/hooks/<this file> → two parents up is repo root.
    return HOOK_DIR.parent.parent


def changed_files(repo: Path) -> list[str]:
    """Return a sorted list of relative paths changed vs HEAD (tracked) plus
    untracked (non-ignored) files. Empty list on any git error."""
    paths: set[str] = set()
    for args in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            result = subprocess.run(
                args,
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        if result.returncode != 0:
            # Not a git repo, or some other git error. Skip silently.
            return []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                paths.add(line)
    return sorted(paths)


def load_triggers() -> list[dict] | None:
    """Parse the YAML config. Returns None (with stderr warning) if pyyaml is
    missing, the file is absent, or the schema is malformed."""
    if not CONFIG_FILE.exists():
        warn(f"config not found: {CONFIG_FILE} (hook is a no-op)")
        return None
    try:
        import yaml  # type: ignore
    except ImportError:
        warn("pyyaml not installed — hook is a no-op. Install: pip install pyyaml")
        return None
    try:
        data = yaml.safe_load(CONFIG_FILE.read_text())
    except yaml.YAMLError as e:
        warn(f"failed to parse {CONFIG_FILE.name}: {e}")
        return None
    if not isinstance(data, dict) or "triggers" not in data:
        warn(f"{CONFIG_FILE.name}: missing top-level 'triggers' key")
        return None
    triggers = data["triggers"]
    if not isinstance(triggers, list):
        warn(f"{CONFIG_FILE.name}: 'triggers' must be a list")
        return None
    return triggers


def glob_match(path: str, pattern: str) -> bool:
    """fnmatch-style glob matching with `**` support for recursive subdir
    matching. `fnmatch` alone treats `**` as `*`, so we normalize."""
    # Normalize `**/` to match any depth including zero. fnmatch treats `*`
    # as "no slashes", so we have to pre-expand `**`.
    if "**" in pattern:
        # Translate **/foo → matches "foo", "a/foo", "a/b/foo", etc.
        # Translate foo/** → matches "foo/", "foo/a", "foo/a/b", etc.
        # Simple approach: build a set of candidate patterns.
        candidates = {pattern.replace("**/", ""), pattern.replace("/**", "")}
        # Also try the original pattern with ** translated to * (single-level).
        candidates.add(pattern.replace("**", "*"))
        return any(fnmatch.fnmatch(path, p) for p in candidates)
    return fnmatch.fnmatch(path, pattern)


def match_triggers(
    files: list[str], triggers: list[dict]
) -> dict[str, list[str]]:
    """For each unique reminder string, collect the list of files that
    triggered it. Returns {reminder: [file, ...]} with reminders in
    first-seen order."""
    reminders: dict[str, list[str]] = {}
    for file in files:
        for trigger in triggers:
            if not isinstance(trigger, dict):
                continue
            pattern = trigger.get("when_changed")
            remind_list = trigger.get("remind", [])
            if not pattern or not remind_list:
                continue
            if not glob_match(file, pattern):
                continue
            for reminder in remind_list:
                reminders.setdefault(reminder, [])
                if file not in reminders[reminder]:
                    reminders[reminder].append(file)
    return reminders


def emit_markdown(reminders: dict[str, list[str]]) -> None:
    """Print a compact markdown reminder block to stdout."""
    print("## Living-docs reminder")
    print()
    print(
        "You edited files with related living artifacts. Before handing back, "
        "verify each item (skip any that already hold):"
    )
    print()
    for reminder, files in reminders.items():
        files_str = ", ".join(f"`{f}`" for f in files)
        print(f"- [ ] {reminder}  \n  _(triggered by: {files_str})_")


def main() -> int:
    triggers = load_triggers()
    if not triggers:
        return 0
    repo = project_root()
    files = changed_files(repo)
    if not files:
        return 0
    reminders = match_triggers(files, triggers)
    if not reminders:
        return 0
    emit_markdown(reminders)
    return 0


if __name__ == "__main__":
    sys.exit(main())

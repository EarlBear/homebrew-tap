"""Discover session files under ~/.claude/projects, deny-by-default.

A project dir under ~/.claude/projects is named after its sanitized cwd (slashes -> -).
We only surface sessions whose slug matches a configured [stages] glob, so personal
projects are never opened. Also provides EarlBear-repo discovery for the POC: given a
root folder, find git repos whose remote points at the EarlBear org.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .stages import slug_matches_any


@dataclass
class SessionFile:
    path: Path
    slug: str
    session_id: str  # filename stem (uuid)
    size: int


def discover_sessions(projects_root: Path, stages: dict[str, str]) -> list[SessionFile]:
    """All *.jsonl sessions whose project slug matches a [stages] glob."""
    out: list[SessionFile] = []
    if not projects_root.exists():
        return out
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir():
            continue
        slug = project_dir.name
        if not slug_matches_any(slug, stages):
            continue
        for jsonl in sorted(project_dir.glob("*.jsonl")):
            try:
                size = jsonl.stat().st_size
            except OSError:
                continue
            out.append(
                SessionFile(path=jsonl, slug=slug, session_id=jsonl.stem, size=size)
            )
    return out


# ---- EarlBear repo discovery (POC sourcing) --------------------------------------

EARLBEAR_REMOTE_MARKERS = ("EarlBear/", "earlbear/", ":EarlBear/", ":earlbear/")


def _git_remote(repo: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def is_earlbear_repo(repo: Path) -> bool:
    remote = _git_remote(repo)
    return any(marker in remote for marker in EARLBEAR_REMOTE_MARKERS)


def find_earlbear_repos(root: Path, max_depth: int = 2) -> list[Path]:
    """Find git repos under `root` whose origin remote points at the EarlBear org."""
    found: list[Path] = []

    def walk(dir_path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if (dir_path / ".git").exists():
            if is_earlbear_repo(dir_path):
                found.append(dir_path)
            return  # don't descend into a repo
        try:
            for child in sorted(dir_path.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    walk(child, depth + 1)
        except OSError:
            return

    walk(root, 0)
    return found


def cwd_to_slug(cwd: Path) -> str:
    """Claude Code's project-dir naming: absolute path with separators replaced by '-'."""
    return str(cwd).replace("/", "-")

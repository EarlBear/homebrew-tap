"""Shared subprocess runner utilities.

ebdeck is a thin wrapper over the deck-cli/docker-compose.yaml toolchain. All
commands ultimately shell out to `docker compose` from the deck-cli root
directory (where docker-compose.yaml lives).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def deck_cli_root() -> Path:
    """Locate the deck-cli directory that contains docker-compose.yaml.

    Resolution order:
    1. $EBDECK_ROOT if set.
    2. Walk up from $PWD looking for docker-compose.yaml alongside a brands/
       directory (distinguishes from other unrelated compose files).
    3. The parent of the src/ebdeck package location (dev install).
    """
    env = os.environ.get("EBDECK_ROOT")
    if env:
        root = Path(env).resolve()
        if (root / "docker-compose.yaml").is_file():
            return root

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "docker-compose.yaml").is_file() and (candidate / "brands").is_dir():
            return candidate

    # Dev install fallback: src/ebdeck/runner.py -> ../../..
    pkg_root = Path(__file__).resolve().parents[2]
    if (pkg_root / "docker-compose.yaml").is_file():
        return pkg_root

    raise SystemExit(
        "ebdeck: could not locate deck-cli/docker-compose.yaml. "
        "Run ebdeck from inside the deck-cli directory, or set $EBDECK_ROOT."
    )


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    """Run a subprocess, streaming output to the user's terminal."""
    where = cwd or deck_cli_root()
    print(f"$ {' '.join(cmd)}  (cwd={where})", file=sys.stderr)
    result = subprocess.run(cmd, cwd=str(where))
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.returncode


def compose(args: list[str], *, check: bool = True) -> int:
    """Run `docker compose <args>` from the deck-cli root."""
    return run(["docker", "compose", *args], check=check)


def brand_prefix(brand: str) -> str:
    """Reproduce Makefile's BRAND_PREFIX = $(basename $(notdir $(BRAND)))."""
    return Path(brand).stem


def content_prefix(content: str) -> str:
    """Reproduce Makefile's CONTENT_PREFIX = $(basename $(CONTENT))."""
    return Path(content).stem

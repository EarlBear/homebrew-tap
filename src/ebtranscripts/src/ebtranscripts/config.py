"""Configuration: ~/.config/earlbear/.env (credentials) + transcripts.toml (policy).

Credentials reuse the existing earlbear convention (SUPABASE_PROJECT_URL,
SUPABASE_SERVICE_ROLE_KEY). Policy lives in transcripts.toml: consent gate, project-slug
-> stage mapping (deny-by-default), per-session overrides, publish allowlist, redaction
extras, and per-model pricing.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("EARLBEAR_CONFIG_DIR", Path.home() / ".config" / "earlbear"))
TOML_PATH = Path(os.environ.get("EBTRANSCRIPTS_TOML", CONFIG_DIR / "transcripts.toml"))
STATE_PATH = Path(
    os.environ.get(
        "EBTRANSCRIPTS_STATE",
        Path.home() / ".local" / "share" / "earlbear" / "ebtranscripts" / "state.json",
    )
)
STAGING_DIR = Path(
    os.environ.get(
        "EBTRANSCRIPTS_STAGING",
        Path.home() / ".local" / "share" / "earlbear" / "ebtranscripts" / "staging",
    )
)

# The temp reconciliation dir for the Google Drive path: raw ~/.claude is scrubbed INTO here,
# the fail-closed gate runs HERE, and only then are verified files rsync'd to the Drive mount.
# Never a target for raw content; scrubbed output only. See drive.py + drive-consolidation-design.
RECONCILE_DIR = Path(
    os.environ.get(
        "EBTRANSCRIPTS_RECONCILE",
        Path.home() / ".local" / "share" / "earlbear" / "ebtranscripts" / "reconcile",
    )
)

DEFAULT_PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# Fallback pricing (USD per million tokens). Zeroed by default — real numbers come from
# transcripts.toml [pricing]. Kept here so cost columns are always populated, never crash.
DEFAULT_PRICING: dict[str, dict[str, float]] = {}


@dataclass
class Config:
    consent: bool = False
    projects_root: Path = DEFAULT_PROJECTS_ROOT
    stages: dict[str, str] = field(default_factory=dict)
    stage_overrides: dict[str, str] = field(default_factory=dict)
    allowlist: dict[str, str] = field(default_factory=dict)
    redact_emails: bool = True
    extra_patterns: list[str] = field(default_factory=list)
    pricing: dict[str, dict[str, float]] = field(default_factory=dict)

    # Credentials (from env). Push targets Supabase when supabase_url/key are set;
    # otherwise, if local_db_url is set, it targets a local Postgres (docker-compose) —
    # the "local mode" for dev/demo without cloud creds. See docs/database-design.md.
    supabase_url: str = ""
    supabase_key: str = ""
    local_db_url: str = ""

    # Google Drive consolidation ([drive] toml table / EBT_DRIVE_DIR). drive_dir points at the
    # local mount root (e.g. ".../Shared drives/agent-workspace/abacus"); the write path
    # partitions it by employee:machine. drive_enabled gates `sync --drive`. No new credentials
    # — Drive membership is the access boundary. See docs/drive-consolidation-design.md.
    drive_dir: str = ""
    drive_enabled: bool = False


def _load_env_file(path: Path) -> None:
    """Minimal .env loader — only sets vars not already in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config() -> Config:
    _load_env_file(CONFIG_DIR / ".env")

    cfg = Config()
    cfg.supabase_url = os.environ.get("SUPABASE_PROJECT_URL", "")
    cfg.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    cfg.local_db_url = os.environ.get("EBT_LOCAL_DB_URL", "")

    if TOML_PATH.exists():
        data = tomllib.loads(TOML_PATH.read_text())
        collection = data.get("collection", {})
        cfg.consent = bool(collection.get("consent", False))
        if collection.get("projects_root"):
            cfg.projects_root = Path(collection["projects_root"]).expanduser()
        cfg.stages = dict(data.get("stages", {}))
        cfg.stage_overrides = dict(data.get("stage_overrides", {}))
        cfg.allowlist = dict(data.get("allowlist", {}))
        redaction = data.get("redaction", {})
        cfg.redact_emails = bool(redaction.get("redact_emails", True))
        cfg.extra_patterns = list(redaction.get("extra_patterns", []))
        cfg.pricing = dict(data.get("pricing", DEFAULT_PRICING))

        drive = data.get("drive", {})
        cfg.drive_dir = str(drive.get("dir", ""))
        cfg.drive_enabled = bool(drive.get("enabled", False))

    # EBT_DRIVE_DIR env wins over the toml (used by the clean-setup sim + tests to point at a
    # throwaway mock mount); setting it also enables the Drive path.
    env_drive = os.environ.get("EBT_DRIVE_DIR", "")
    if env_drive:
        cfg.drive_dir = env_drive
        cfg.drive_enabled = True

    return cfg

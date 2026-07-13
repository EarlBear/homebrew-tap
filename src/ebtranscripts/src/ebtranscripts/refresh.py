"""Load consolidated telemetry from the Google Drive mount into the DB — the read side.

The mirror of drive.py: many machines write scrubbed `derived.json` files into the shared Drive
folder; this module walks that folder from ANY one machine and upserts each derived record into
the configured DB (Supabase or local Postgres) via the SAME push path, then refreshes the marts.
There is exactly ONE aggregation engine (refresh_cc_marts()) — this does not re-implement it.

    drive_dir/<employee>:<machine>/projects/<slug>/derived.json   (+ .sync.json marker)

`derived.json` powers the session-level marts; `events.ndjson` (when present) is loaded into
`cc_events` for the per-session cost timeline. Both are read only from project dirs that carry a
`.sync.json` completion marker, so a
half-synced dir (Drive copying files up in the background) is skipped until it is complete.
Google Drive junk (`.gdoc`, `desktop.ini`, `*.tmp`, `.DS_Store`) is ignored by construction —
we glob for the exact `derived.json` name, not a wildcard.

Importable (`from ebtranscripts.refresh import refresh_from_drive`) so both the CLI subcommand
`ebtranscripts refresh-from-drive` and the standalone `scripts/refresh-from-drive.py` wrapper
share one implementation. Idempotent: upsert-on-PK means re-running over the same Drive dir
leaves row counts unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import STATE_PATH, Config
from .models import ExtractResult
from .push import events_to_rows, make_pusher


@dataclass
class RefreshResult:
    sessions: int = 0                       # derived.json files upserted this run
    events_loaded: int = 0                  # cc_events rows loaded from events.ndjson this run
    skipped_incomplete: int = 0             # project dirs without a .sync.json marker
    skipped_unchanged: int = 0              # sessions whose derived_hash matched the watermark
    marts_refreshed: bool = False           # whether refresh_cc_marts() was called (>=1 change)
    errors: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)


def _watermark_path(watermark_dir: Path | None = None) -> Path:
    """Per-machine refresh watermark: session_id -> last-loaded derived_hash, keyed by drive dir."""
    base = Path(watermark_dir) if watermark_dir is not None else STATE_PATH.parent
    return base / "refresh-watermark.json"


def _load_watermark(drive_key: str, watermark_dir: Path | None = None) -> dict[str, str]:
    p = _watermark_path(watermark_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()).get(drive_key, {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_watermark(
    drive_key: str, marks: dict[str, str], watermark_dir: Path | None = None
) -> None:
    p = _watermark_path(watermark_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        allw = json.loads(p.read_text()) if p.exists() else {}
    except (json.JSONDecodeError, OSError):
        allw = {}
    allw[drive_key] = marks
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(allw, indent=2))
    tmp.replace(p)


def _derived_files(drive_root: Path):
    """Yield each project dir's derived.json (abacus/<employee:machine>/projects/<slug>/)."""
    yield from sorted(drive_root.glob("*/projects/*/derived.json"))


def refresh_from_drive(drive_dir: str | Path, cfg: Config, *, full: bool = False,
                       watermark_dir: Path | None = None) -> RefreshResult:
    """Upsert CHANGED sessions' derived records from the Drive dir; refresh marts if any changed.

    Incremental by default: each session's `.sync.json` carries a `derived_hash`; a session whose
    hash matches the stored watermark since the last refresh is SKIPPED (no re-push). The marts are
    rebuilt only when at least one session actually changed — so "do we need to re-calc?" is
    answered by the watermark, not by re-doing all the work. Pass `full=True` to force a re-push of
    every session (ignores the watermark). Idempotent either way (upsert on PK).

    Raises FileNotFoundError if the Drive dir is missing; RuntimeError (from make_pusher) if no
    DB target is configured. Malformed derived.json files are collected into result.errors.
    """
    drive_root = Path(drive_dir).expanduser()
    if not drive_root.exists():
        raise FileNotFoundError(f"drive dir not found / not mounted: {drive_root}")

    drive_key = str(drive_root.resolve())
    watermark = {} if full else _load_watermark(drive_key, watermark_dir)
    pusher = make_pusher(
        supabase_url=cfg.supabase_url,
        supabase_key=cfg.supabase_key,
        local_db_url=cfg.local_db_url,
    )

    out = RefreshResult()
    new_marks = dict(watermark)  # carry forward, update the ones we (re)load
    for derived in _derived_files(drive_root):
        project_dir = derived.parent
        marker_path = project_dir / ".sync.json"
        if not marker_path.exists():
            # Incomplete (marker written last) — skip until Drive finishes syncing it up.
            out.skipped_incomplete += 1
            continue
        try:
            marker = json.loads(marker_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            out.errors.append(f"{marker_path}: {e}")
            continue
        sid = marker.get("session_id", str(derived))
        cur_hash = marker.get("derived_hash", "")
        # Watermark skip: unchanged derived record since last refresh -> nothing to re-push.
        if not full and cur_hash and watermark.get(sid) == cur_hash:
            out.skipped_unchanged += 1
            continue
        try:
            result = ExtractResult.model_validate_json(derived.read_text())
        except Exception as e:  # malformed / partially-synced file — record and continue.
            out.errors.append(f"{derived}: {e}")
            continue
        pusher.push(result)
        out.sessions += 1
        out.session_ids.append(result.session.session_id)

        # Load the sibling event log into cc_events (idempotent on session_id+seq). Only for
        # changed sessions (we're already past the watermark skip), so events stay incremental.
        events_path = project_dir / "events.ndjson"
        if events_path.exists():
            try:
                events = [json.loads(ln) for ln in events_path.read_text().splitlines()
                          if ln.strip()]
            except json.JSONDecodeError as e:
                out.errors.append(f"{events_path}: {e}")
                events = []
            if events:
                rows = events_to_rows(
                    result.session.session_id, events,
                    machine_id=result.session.machine_id, machine=result.session.machine,
                )
                out.events_loaded += pusher.push_events(rows)

        if cur_hash:
            new_marks[sid] = cur_hash

    # Rebuild the marts ONLY if something changed — knowing a re-calc is needed is the point.
    if out.sessions > 0:
        pusher.refresh_marts()
        out.marts_refreshed = True

    _save_watermark(drive_key, new_marks, watermark_dir)
    return out

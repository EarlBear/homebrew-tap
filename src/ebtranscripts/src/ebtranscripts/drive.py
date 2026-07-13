"""Write derived telemetry + an event append-log to a shared Google Drive mount — fail-closed.

This is the single most load-bearing security control in the Drive-consolidation feature:
Google Drive becomes a new exfiltration path, so NOTHING reaches it that has not been built from
a safe-field allowlist and independently verified. We do NOT ship the full transcript — the
artifacts are derived.json (metrics) and events.ndjson (an allowlist-built event append-log),
both serialized from already-safe derived records, so no raw body is ever copied. The flow
(docs/drive-consolidation-design.md):

    ~/.claude/projects/<slug>/<id>.jsonl   READ-ONLY source (never modified here)
          │  read only
          ▼
    temp reconcile dir  (config.RECONCILE_DIR/<drive_user_id>/projects/<slug>/)
          │  1. build derived.json + events.ndjson (both from the ExtractResult — allowlist)
          │  2. FAIL-CLOSED GATE, in order:
          │       a. run_self_test()          — planted-secret fixture gate
          │       b. gitleaks MUST be present  — else refuse (brew install gitleaks)
          │       c. scan_clean_strict() == True on BOTH files (0 findings)
          ▼
    Google Drive mount  (drive_dir/<drive_user_id>/projects/<slug>/)
          │  3. copy the verified files up; write .sync.json completion marker LAST

If ANY gate step fails, DriveGateError is raised and nothing is copied to Drive. The reconcile
dir holds only allowlist-built output; raw content is never written anywhere but its original
read-only home under ~/.claude. events.ndjson is append-only (NDJSON), so it fits the byte-offset
delta-sync model; we deliberately do NOT gzip it (gzip breaks true append + human-readability;
files are KB-scale). See docs/decisions.md (2026-07-08).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import RECONCILE_DIR, Config
from .events import plan_incremental_append
from .identity import drive_user_id, machine_identity
from .models import ExtractResult
from .selftest import run_self_test
from .verify import gitleaks_available, scan_clean_strict


class DriveGateError(RuntimeError):
    """Raised when the fail-closed write-to-Drive gate refuses. Nothing was copied."""


@dataclass
class DriveWriteResult:
    project_dir: Path          # the Drive dir the files landed in
    wrote_events: bool         # whether an events.ndjson append-log was written
    files: list[str]           # basenames written
    events_appended: int = 0   # new event lines appended this sync (0 on a rewrite)
    events_rewritten: bool = False  # True if the log was fully recomputed (rewind/first write)
    derived_hash: str = ""     # sha256 of derived.json (the refresh watermark)


def _project_rel(drive_uid: str, project_slug: str) -> Path:
    return Path(drive_uid) / "projects" / project_slug


def write_to_drive(
    result: ExtractResult,
    raw_text: str,
    cfg: Config,
    *,
    identity: tuple[str, str] | None = None,
    write_events: bool = True,
    reconcile_root: Path | None = None,
) -> DriveWriteResult:
    """Build the clean artifacts, gate (fail-closed), and copy them to the Drive mount.

    The artifacts are derived.json (session metrics) and events.ndjson (an allowlist-built
    event append-log — tool calls, subagent/skill runs, a metrics snapshot). Both are
    CONSTRUCTED from already-safe derived records; we do NOT ship the full transcript, so no raw
    body is ever copied. `raw_text` (the RAW ~/.claude JSONL) is accepted for interface
    stability but is not written anywhere — the event log comes from `result`. Raises
    DriveGateError if the Drive dir is unset/absent, gitleaks is missing, the self-test fails,
    or any artifact still trips gitleaks.
    """
    if not cfg.drive_dir:
        raise DriveGateError("no drive_dir configured (set [drive].dir or EBT_DRIVE_DIR).")
    drive_root = Path(cfg.drive_dir).expanduser()
    if not drive_root.exists():
        raise DriveGateError(f"drive_dir does not exist / not mounted: {drive_root}")

    ident = identity if identity is not None else machine_identity()
    drive_uid = drive_user_id(ident)
    slug = result.session.project_slug

    # ---- Build the clean files in the temp reconcile dir (never Drive directly) ----
    recon_root = (reconcile_root or RECONCILE_DIR).expanduser()
    recon_dir = recon_root / _project_rel(drive_uid, slug)
    recon_dir.mkdir(parents=True, exist_ok=True)

    derived_path = recon_dir / "derived.json"
    derived_path.write_text(result.model_dump_json(indent=2))

    # Incremental event log: the reconcile dir's existing events.ndjson IS the watermark. On a
    # growing session we APPEND only the new body lines (and rewrite the moving snapshot footer);
    # a /rewind that rewrote earlier events forces a full recompute. See plan_incremental_append.
    events_path = recon_dir / "events.ndjson"
    wrote_events = False
    events_appended = 0
    events_rewritten = False
    gate_slice = ""  # the bytes we must gitleaks-scan (appended slice, or whole file on rewrite)
    if write_events:
        existing = events_path.read_text() if events_path.exists() else None
        plan = plan_incremental_append(result, existing)
        if plan.rewrite:
            events_path.write_text(plan.full_text)
            gate_slice = plan.full_text
            events_rewritten = True
        else:
            # Append the new body tail, then rewrite the moving footer (snapshot totals).
            body = "\n".join(ln for ln in existing.splitlines()
                             if ln.strip() and json.loads(ln).get("kind") != "metrics_snapshot")
            new_body = "\n".join([body, *plan.append_lines]) if plan.append_lines else body
            events_path.write_text(new_body + "\n" + plan.footer_line + "\n")
            gate_slice = "\n".join([*plan.append_lines, plan.footer_line])
            events_appended = len(plan.append_lines)
        wrote_events = True

    # ---- FAIL-CLOSED GATE (order matters) ----
    # (a) planted-secret self-test.
    if not run_self_test():
        raise DriveGateError("sanitizer self-test failed — refusing to write to Drive.")
    # (b) gitleaks is REQUIRED on this boundary (unlike the best-effort render path).
    if not gitleaks_available():
        raise DriveGateError(
            "gitleaks is required for Drive writes but is not installed. "
            "Install it (`brew install gitleaks`) and retry."
        )
    # (c) independent strict scan. derived.json is rebuilt each sync (scan whole); events.ndjson
    #     is append-only, so we scan only what's NEW this sync (the appended slice / rewrite).
    to_verify = [("derived.json", derived_path.read_text())]
    if wrote_events:
        to_verify.append(("events.ndjson (new)", gate_slice))
    for name, content in to_verify:
        if content.strip() and not scan_clean_strict(content):
            raise DriveGateError(
                f"{name} still trips gitleaks; refusing to write to Drive."
            )

    # ---- Copy verified files UP to Drive; .sync.json marker LAST ----
    drive_dir = drive_root / _project_rel(drive_uid, slug)
    drive_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    shutil.copy2(derived_path, drive_dir / "derived.json")
    written.append("derived.json")
    if wrote_events:
        shutil.copy2(events_path, drive_dir / "events.ndjson")
        written.append("events.ndjson")

    # The completion marker is written LAST so a partially-synced dir (Drive copying files up in
    # the background) is distinguishable from a complete one — refresh_from_drive only reads dirs
    # that have it. It records identity + versions + a derived_hash (the refresh watermark uses
    # it to skip sessions whose derived record is unchanged) + append/rewrite bookkeeping. No
    # secrets.
    derived_hash = hashlib.sha256(derived_path.read_text().encode()).hexdigest()
    marker = {
        "session_id": result.session.session_id,
        "project_slug": slug,
        "machine_id": ident[0],
        "machine": ident[1],
        "drive_user_id": drive_uid,
        "sanitizer_version": result.session.sanitizer_version,
        "extractor_version": result.session.extractor_version,
        "has_events": wrote_events,
        "events_appended": events_appended,
        "events_rewritten": events_rewritten,
        "derived_hash": derived_hash,
        "files": written,
    }
    (drive_dir / ".sync.json").write_text(json.dumps(marker, indent=2))
    written.append(".sync.json")

    return DriveWriteResult(
        project_dir=drive_dir, wrote_events=wrote_events, files=written,
        events_appended=events_appended, events_rewritten=events_rewritten,
        derived_hash=derived_hash,
    )

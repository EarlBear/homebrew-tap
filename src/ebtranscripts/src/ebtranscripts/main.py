"""ebtranscripts — extract Claude Code session telemetry, sanitize at the edge, and
publish sanitized transcripts.

Consent-gated and deny-by-default: extract/push refuse until consent=true in
transcripts.toml, and only project slugs matched by [stages] are ever opened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import STAGING_DIR, STATE_PATH, TOML_PATH, load_config
from .extract import extract_session
from .identity import drive_user_id, machine_identity
from .sanitizer import SANITIZER_VERSION, redact
from .scan import discover_sessions, find_earlbear_repos
from .selftest import PLANTED_SECRETS, assemble_fixture, run_self_test
from .state import FileState, State, _prefix_hash, file_unchanged, read_full

app = typer.Typer(
    name="ebtranscripts",
    help="Extract Claude Code session telemetry, sanitize at the edge, publish transcripts.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err = Console(stderr=True)


def _require_consent(cfg) -> None:
    if not cfg.consent:
        err.print(
            "[red]Consent required.[/red] Set consent = true under [collection] in "
            "transcripts.toml after reading the what-we-collect notice."
        )
        raise typer.Exit(2)


@app.command()
def scan(
    full: bool = typer.Option(False, "--full", help="Ignore stored offsets."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Discover in-scope sessions and show which have new bytes."""
    cfg = load_config()
    sessions = discover_sessions(cfg.projects_root, cfg.stages)
    state = State(STATE_PATH)
    rows = []
    for sf in sessions:
        prior = state.get(str(sf.path))
        new_bytes = sf.size if full else max(0, sf.size - prior.offset)
        rows.append(
            {
                "session_id": sf.session_id,
                "slug": sf.slug,
                "size": sf.size,
                "new_bytes": new_bytes,
            }
        )
    if as_json:
        console.print_json(data=rows)
        return
    if not rows:
        console.print("No in-scope sessions found. Check [stages] in transcripts.toml.")
        return
    table = Table("session", "slug", "size", "new bytes")
    for r in rows:
        table.add_row(r["session_id"][:8], r["slug"], str(r["size"]), str(r["new_bytes"]))
    console.print(table)


@app.command()
def extract(
    session: str = typer.Option("", "--session", help="Only this session id."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not write staging."),
) -> None:
    """Parse -> sanitize -> write normalized records to the staging dir."""
    cfg = load_config()
    _require_consent(cfg)
    sessions = discover_sessions(cfg.projects_root, cfg.stages)
    if session:
        sessions = [s for s in sessions if s.session_id == session]
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for sf in sessions:
        text = read_full(sf.path)
        result = extract_session(
            text,
            sf.slug,
            cfg.stages,
            cfg.stage_overrides,
            cfg.pricing,
            redact_emails=cfg.redact_emails,
            extra_patterns=cfg.extra_patterns,
        )
        if result is None:
            continue
        if not dry_run:
            out = STAGING_DIR / f"{result.session.session_id}.json"
            out.write_text(result.model_dump_json(indent=2))
        count += 1
    console.print(f"Extracted {count} session(s){' (dry run)' if dry_run else ''}.")


@app.command()
def sanitize(
    check: str = typer.Option("", "--check", help="Redact a file's text and print it."),
    self_test: bool = typer.Option(False, "--self-test", help="Run the planted-secret fixtures."),
) -> None:
    """Standalone redaction. --self-test fails closed if any planted secret survives."""
    if self_test:
        ok = _run_self_test()
        if ok:
            console.print(f"[green]Sanitizer self-test passed[/green] (v{SANITIZER_VERSION}).")
            raise typer.Exit(0)
        err.print("[red]Sanitizer self-test FAILED — a planted secret survived.[/red]")
        raise typer.Exit(1)
    if check:
        text = Path(check).read_text()
        console.print(redact(text))
        return
    err.print("Nothing to do. Use --self-test or --check FILE.")
    raise typer.Exit(2)


# The planted-secret self-test lives in selftest.py so non-CLI modules (drive.py) can run the
# same fail-closed gate without importing this Typer app. Re-exported here under the historical
# private names so existing call sites are unchanged. The fixture is now assembled at runtime
# from a placeholder template (no secret-shaped text is committed) — see selftest.py.
_assemble_fixture = assemble_fixture
_PLANTED_SECRETS = PLANTED_SECRETS
_run_self_test = run_self_test


@app.command()
def push(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not call Supabase."),
    publish: str = typer.Option("", "--publish", help="Mark this session id published."),
    refresh_marts: bool = typer.Option(True, "--refresh-marts/--no-refresh-marts"),
) -> None:
    """Upsert staged records to Supabase (idempotent). Runs the sanitizer self-test first."""
    cfg = load_config()
    _require_consent(cfg)
    if not _run_self_test():
        err.print("[red]Sanitizer self-test failed — refusing to push.[/red]")
        raise typer.Exit(1)
    if not (cfg.supabase_url and cfg.supabase_key) and not cfg.local_db_url:
        err.print(
            "[red]No push target.[/red] Set SUPABASE_PROJECT_URL/SUPABASE_SERVICE_ROLE_KEY, "
            "or EBT_LOCAL_DB_URL for local Postgres mode."
        )
        raise typer.Exit(2)

    from .models import ExtractResult
    from .push import make_pusher

    staged = sorted(STAGING_DIR.glob("*.json"))
    if dry_run:
        console.print(f"Would push {len(staged)} staged session(s).")
        return

    pusher = make_pusher(
        supabase_url=cfg.supabase_url,
        supabase_key=cfg.supabase_key,
        local_db_url=cfg.local_db_url,
    )
    totals: dict[str, int] = {}
    for f in staged:
        result = ExtractResult.model_validate_json(f.read_text())
        counts = pusher.push(result)
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
    if refresh_marts:
        pusher.refresh_marts()
    if publish:
        pusher.set_published(publish, f"/transcripts/{publish}/")
    console.print(f"Pushed: {json.dumps(totals)}")


@app.command()
def sync(
    quiet: bool = typer.Option(False, "--quiet"),
    to_drive: bool = typer.Option(
        False, "--drive",
        help="Also scrub + write each session to the Google Drive mount (fail-closed gate).",
    ),
) -> None:
    """scan -> extract -> push (-> optionally write scrubbed files to Drive). Automation entry."""
    ctx_extract(quiet, to_drive=to_drive)


def ctx_extract(quiet: bool, *, to_drive: bool = False) -> None:
    cfg = load_config()
    _require_consent(cfg)
    # Per-employee/per-machine attribution, derived once for this sync run.
    identity = machine_identity()
    sessions = discover_sessions(cfg.projects_root, cfg.stages)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    state = State(STATE_PATH)
    n = 0
    skipped = 0
    # When writing to Drive we need the raw text alongside the result; keep the pairs for
    # changed sessions so the fail-closed gate can scrub them after the self-test passes.
    drive_batch: list[tuple[object, str]] = []
    for sf in sessions:
        # Delta-aware: skip sessions unchanged since the last sync (same size, inode, and
        # content-prefix hash — so an in-place /rewind still counts as changed).
        if file_unchanged(sf.path, state.get(str(sf.path))):
            skipped += 1
            continue
        text = read_full(sf.path)  # ~/.claude is read-only; we only ever read it.
        result = extract_session(
            text, sf.slug, cfg.stages, cfg.stage_overrides, cfg.pricing,
            redact_emails=cfg.redact_emails, extra_patterns=cfg.extra_patterns,
            identity=identity,
        )
        if result is None:
            continue
        (STAGING_DIR / f"{result.session.session_id}.json").write_text(
            result.model_dump_json(indent=2)
        )
        if to_drive:
            drive_batch.append((result, text))
        stat = sf.path.stat()
        with sf.path.open("rb") as fh:
            prefix = _prefix_hash(fh, stat.st_size)
        state.set(
            str(sf.path),
            FileState(offset=stat.st_size, size=stat.st_size, inode=stat.st_ino,
                      session_id=result.session.session_id, prefix_hash=prefix),
        )
        n += 1
    state.save()
    if not quiet:
        console.print(f"Synced {n} changed session(s); skipped {skipped} unchanged.")
    has_target = (cfg.supabase_url and cfg.supabase_key) or cfg.local_db_url
    if has_target and _run_self_test():
        from .models import ExtractResult
        from .push import make_pusher

        pusher = make_pusher(
            supabase_url=cfg.supabase_url,
            supabase_key=cfg.supabase_key,
            local_db_url=cfg.local_db_url,
        )
        for f in sorted(STAGING_DIR.glob("*.json")):
            pusher.push(ExtractResult.model_validate_json(f.read_text()))
        pusher.refresh_marts()
        if not quiet:
            target = "Supabase" if cfg.supabase_url else "local Postgres"
            console.print(f"Pushed staged sessions to {target}.")

    if to_drive:
        _write_batch_to_drive(cfg, identity, drive_batch, quiet)


def _write_batch_to_drive(cfg, identity, drive_batch, quiet) -> None:
    """Run the fail-closed Drive gate for each changed session. Refuses loudly, never silently."""
    from .drive import DriveGateError, write_to_drive

    if not cfg.drive_dir:
        err.print("[red]--drive given but no drive_dir configured "
                  "(set [drive].dir or EBT_DRIVE_DIR).[/red]")
        raise typer.Exit(2)
    wrote = 0
    for result, raw_text in drive_batch:
        try:
            write_to_drive(result, raw_text, cfg, identity=identity)
            wrote += 1
        except DriveGateError as e:
            err.print(f"[red]Drive write refused: {e}[/red]")
            raise typer.Exit(1) from e
    if not quiet:
        console.print(f"Wrote {wrote} scrubbed session(s) to the Drive mount.")


@app.command(name="refresh-from-drive")
def refresh_from_drive_cmd(
    drive_dir: str = typer.Argument(
        "", help="Drive mount root (the abacus dir). Defaults to [drive].dir / EBT_DRIVE_DIR."
    ),
    quiet: bool = typer.Option(False, "--quiet"),
    full: bool = typer.Option(
        False, "--full", help="Re-push every session, ignoring the change watermark."
    ),
) -> None:
    """Load CHANGED sessions from the Drive dir into the DB; refresh marts only if anything changed.

    Incremental by default (a per-session watermark skips unchanged derived records). Use --full
    to force a re-push of everything.
    """
    from .refresh import refresh_from_drive

    cfg = load_config()
    target = drive_dir or cfg.drive_dir
    if not target:
        err.print("[red]No Drive dir: pass one, or set [drive].dir / EBT_DRIVE_DIR.[/red]")
        raise typer.Exit(2)
    if not (cfg.supabase_url and cfg.supabase_key) and not cfg.local_db_url:
        err.print("[red]No DB target: set SUPABASE_* or EBT_LOCAL_DB_URL.[/red]")
        raise typer.Exit(2)
    result = refresh_from_drive(target, cfg, full=full)
    if not quiet:
        marts = "refreshed" if result.marts_refreshed else "unchanged (nothing new)"
        console.print(
            f"Loaded {result.sessions} changed session(s) + {result.events_loaded} event(s); "
            f"skipped {result.skipped_unchanged} unchanged + {result.skipped_incomplete} "
            f"incomplete; marts {marts}; {len(result.errors)} error(s)."
        )
        for e in result.errors:
            err.print(f"[yellow]  {e}[/yellow]")


@app.command()
def status(as_json: bool = typer.Option(False, "--json")) -> None:
    """Show discovered sessions, offsets, and staged record counts."""
    cfg = load_config()
    sessions = discover_sessions(cfg.projects_root, cfg.stages)
    staged = sorted(STAGING_DIR.glob("*.json"))
    data = {
        "in_scope_sessions": len(sessions),
        "staged": len(staged),
        "allowlist": len(cfg.allowlist),
        "consent": cfg.consent,
        "sanitizer_version": SANITIZER_VERSION,
    }
    if as_json:
        console.print_json(data=data)
        return
    for k, v in data.items():
        console.print(f"{k}: {v}")


@app.command()
def doctor() -> None:
    """Check env, config, fixtures, and consent."""
    import os

    from .verify import gitleaks_available

    cfg = load_config()
    # A machine needs SOME telemetry target: Supabase, a local DB, or the Drive corpus. When
    # Drive or a local DB is configured, Supabase creds are optional (informational), so a
    # Drive-only / local-only machine can still be green. When none is configured, having a
    # Supabase target is required.
    has_supabase = bool(cfg.supabase_url and cfg.supabase_key)
    has_other_target = bool(cfg.local_db_url) or bool(cfg.drive_dir) or cfg.drive_enabled
    checks = [
        ("consent granted", cfg.consent),
        ("stage mapping present", bool(cfg.stages)),
        ("projects root exists", cfg.projects_root.exists()),
        ("a telemetry target is configured (Supabase / local DB / Drive)",
         has_supabase or has_other_target),
        ("gitleaks available (2nd-layer verify)", gitleaks_available()),
        ("sanitizer self-test", _run_self_test()),
    ]

    # Google Drive consolidation rows. When [drive] is enabled these are REQUIRED (the mount
    # must exist + be writable, and gitleaks is mandatory on that boundary); when it's off they
    # are informational only, so an unconfigured machine still passes doctor.
    if cfg.drive_enabled or cfg.drive_dir:
        drive_root = Path(cfg.drive_dir).expanduser() if cfg.drive_dir else None
        mounted = bool(drive_root and drive_root.exists())
        writable = bool(drive_root and mounted and os.access(drive_root, os.W_OK))
        checks += [
            (f"drive mount present ({cfg.drive_dir or 'unset'})", mounted),
            ("drive mount writable", writable),
            ("gitleaks installed (REQUIRED for Drive writes)", gitleaks_available()),
            (f"machine identity ({drive_user_id()})", True),
        ]

    table = Table("check", "ok")
    all_ok = True
    for name, ok in checks:
        table.add_row(name, "[green]yes[/green]" if ok else "[red]no[/red]")
        all_ok = all_ok and ok
    console.print(table)
    raise typer.Exit(0 if all_ok else 1)


@app.command(name="protect-paths")
def protect_paths(
    settings_path: str = typer.Option(
        "", "--settings",
        help="Path to settings.json (default: ~/.claude/settings.json).",
    ),
) -> None:
    """Upsert the read-only deny rules (~/.claude + Drive output) into settings.json.

    Idempotent: creates the file if missing, merges the deny rules without clobbering existing
    keys, and is a no-op if they are already present. Enforces the immutability invariant of the
    Drive-consolidation feature as a Claude Code permission.
    """
    from .settings_upsert import upsert_settings_file

    default_target = Path.home() / ".claude" / "settings.json"
    target = Path(settings_path).expanduser() if settings_path else default_target
    try:
        added = upsert_settings_file(target)
    except ValueError as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    if added:
        console.print(f"Added {len(added)} deny rule(s) to {target}.")
        for rule in added:
            console.print(f"  + {rule}")
    else:
        console.print(f"All deny rules already present in {target} (no change).")


@app.command()
def allow(
    session_id: str = typer.Argument(..., help="Session id to allowlist for publishing."),
    title: str = typer.Option("", "--title", help="Human-readable title."),
) -> None:
    """Add a session to the publish allowlist in transcripts.toml."""
    if not TOML_PATH.exists():
        err.print(f"[red]No config at {TOML_PATH}.[/red]")
        raise typer.Exit(2)
    text = TOML_PATH.read_text()
    line = f'"{session_id}" = "{title or session_id}"'
    if "[allowlist]" in text:
        text = text.replace("[allowlist]", f"[allowlist]\n{line}", 1)
    else:
        text = text.rstrip() + f"\n\n[allowlist]\n{line}\n"
    TOML_PATH.write_text(text)
    console.print(f"Allowlisted {session_id}.")


@app.command()
def render(
    session: str = typer.Option(..., "--session", help="Session id to render."),
    out: str = typer.Option("", "-o", "--out", help="Output dir (default: ./transcripts)."),
    preview: bool = typer.Option(
        False, "--preview", help="Render even if not allowlisted, to scratch only."
    ),
) -> None:
    """Sanitize + render an allowlisted session to themed HTML via claude-code-transcripts."""
    cfg = load_config()
    _require_consent(cfg)
    if not _run_self_test():
        err.print("[red]Sanitizer self-test failed — refusing to render.[/red]")
        raise typer.Exit(1)

    from .render import render_session

    sessions = discover_sessions(cfg.projects_root, cfg.stages)
    match = next((s for s in sessions if s.session_id == session), None)
    if match is None:
        err.print(f"[red]Session {session} not found in scope.[/red]")
        raise typer.Exit(2)

    allowlisted = session in cfg.allowlist
    if not allowlisted and not preview:
        err.print(
            f"[red]{session} is not allowlisted.[/red] Run `ebtranscripts allow {session}` "
            "or pass --preview to render to scratch only."
        )
        raise typer.Exit(2)

    # Honor an explicit -o; otherwise default to ./transcripts (or a scratch dir when
    # previewing a non-allowlisted session so it never lands in a publish location).
    if out:
        out_dir = Path(out).expanduser()
    elif preview and not allowlisted:
        out_dir = Path.cwd() / ".transcript-preview"
    else:
        out_dir = Path.cwd() / "transcripts"

    raw = read_full(match.path)
    entry = render_session(
        raw, session, out_dir,
        redact_emails=cfg.redact_emails, extra_patterns=cfg.extra_patterns,
    )
    entry["title"] = cfg.allowlist.get(session, session)
    entry["stage"] = None
    entry["sanitizer_version"] = SANITIZER_VERSION

    # Update the site manifest so the transcripts index can list it.
    manifest_path = out_dir / "manifest.json"
    manifest = {"sessions": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            pass
    manifest["sessions"] = [
        s for s in manifest.get("sessions", []) if s.get("session_id") != session
    ] + [entry]
    manifest_path.write_text(json.dumps(manifest, indent=2))
    console.print(f"Rendered {session} ({entry['pages']} pages) to {out_dir / session}.")


@app.command("find-repos")
def find_repos(
    root: str = typer.Argument(..., help="Folder to scan for EarlBear git repos."),
) -> None:
    """POC helper: list git repos under ROOT whose remote points at the EarlBear org."""
    repos = find_earlbear_repos(Path(root).expanduser())
    for r in repos:
        console.print(str(r))
    if not repos:
        console.print("No EarlBear repos found.")


@app.command()
def version() -> None:
    """Print the version."""
    console.print(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(app())

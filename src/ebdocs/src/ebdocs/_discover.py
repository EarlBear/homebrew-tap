"""discover command implementation — use-case browser for ebdocs.

Reads use-cases.yaml from the package directory and renders curated
use cases. This is NOT a help replacement — use `ebdocs --help` for
command syntax. discover is for real-world patterns and worked examples.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

# Path to the use-cases corpus, co-located with this module
_USE_CASES_FILE = Path(__file__).parent / "use-cases.yaml"

_FOOTER = (
    "\nFor command syntax:  ebdocs --help  or  ebdocs <group> --help\n"
    "For JSON output:     ebdocs --help-json\n"
    "To add a use case:   edit gdocs-cli/src/ebdocs/use-cases.yaml  "
    "or run  /capture-cli-use-case\n"
)


def _load_use_cases() -> list[dict]:
    try:
        import yaml
    except ImportError:
        typer.echo(
            "[discover] pyyaml not installed — run `pip install pyyaml`",
            err=True,
        )
        return []

    if not _USE_CASES_FILE.exists():
        typer.echo(f"[discover] use-cases file not found: {_USE_CASES_FILE}", err=True)
        return []

    try:
        data = yaml.safe_load(_USE_CASES_FILE.read_text())
    except yaml.YAMLError as e:
        typer.echo(f"[discover] malformed YAML in use-cases.yaml: {e}", err=True)
        return []

    return data.get("use_cases", []) if isinstance(data, dict) else []


def _filter_by_tag(use_cases: list[dict], tag: Optional[str]) -> list[dict]:
    if not tag:
        return use_cases
    return [uc for uc in use_cases if tag in (uc.get("tags") or [])]


def _filter_stale(use_cases: list[dict], days: int) -> list[dict]:
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    stale = []
    for uc in use_cases:
        lv = uc.get("last_verified")
        if not lv:
            stale.append(uc)
            continue
        try:
            from datetime import date as _date
            verified = _date.fromisoformat(str(lv))
            if verified < cutoff:
                stale.append(uc)
        except ValueError:
            stale.append(uc)
    return stale


def _render_human(use_cases: list[dict], detail_id: Optional[str] = None) -> None:
    if detail_id:
        matches = [uc for uc in use_cases if uc.get("id") == detail_id]
        if not matches:
            typer.echo(f"No use case with id '{detail_id}'. Run `ebdocs discover` to list all.", err=True)
            raise typer.Exit(1)
        _render_detail(matches[0])
        return

    if not use_cases:
        typer.echo("No use cases found.")
        typer.echo(_FOOTER)
        return

    groups: dict[str, list[dict]] = {}
    for uc in use_cases:
        tags = uc.get("tags") or []
        key = tags[0] if tags else "other"
        groups.setdefault(key, []).append(uc)

    for group, items in sorted(groups.items()):
        typer.echo(f"\n[{group}]")
        for uc in items:
            typer.echo(f"  {uc.get('id', '?'):<40}  {uc.get('title', '')}")
            when = uc.get("when", "")
            if when:
                typer.echo(f"    when: {when}")

    typer.echo(_FOOTER)


def _render_detail(uc: dict) -> None:
    typer.echo(f"\n# {uc.get('title', uc.get('id'))}")
    typer.echo(f"id:            {uc.get('id', '')}")
    typer.echo(f"when:          {uc.get('when', '')}")
    typer.echo(f"tags:          {', '.join(uc.get('tags') or [])}")
    typer.echo(f"last_verified: {uc.get('last_verified', 'unknown')}")
    typer.echo("\nCommands:")
    for cmd in uc.get("commands") or []:
        typer.echo(f"  {cmd}")
    notes = uc.get("notes", "").strip()
    if notes:
        typer.echo("\nNotes:")
        for line in notes.splitlines():
            typer.echo(f"  {line}")
    typer.echo(_FOOTER)


def _render_json(use_cases: list[dict]) -> None:
    print(json.dumps({"use_cases": use_cases}, indent=2, default=str))


def _render_markdown(use_cases: list[dict]) -> None:
    typer.echo("| ID | Title | When | Tags |")
    typer.echo("|----|-------|------|------|")
    for uc in use_cases:
        tags = ", ".join(uc.get("tags") or [])
        title = uc.get("title", "")
        when = uc.get("when", "")
        uid = uc.get("id", "")
        typer.echo(f"| `{uid}` | {title} | {when} | {tags} |")
    typer.echo(
        "\n> For detail on a use case: `ebdocs discover <id>`  \n"
        "> To add an entry: edit `gdocs-cli/src/ebdocs/use-cases.yaml` "
        "or run `/capture-cli-use-case`"
    )


def discover_command(
    use_case_id: Optional[str] = typer.Argument(
        None, help="Show full detail for a specific use case (by id)."
    ),
    tag: Optional[str] = typer.Option(
        None, "--tag", "-t", help="Filter by tag (e.g. watson, auth, doc)."
    ),
    stale: Optional[int] = typer.Option(
        None, "--stale", help="List use cases not verified in N days (default 180).",
        is_flag=False, flag_value=180,
    ),
    fmt: str = typer.Option(
        "human", "--format", "-f",
        help="Output format: human (default), json, md.",
    ),
) -> None:
    """Browse real use cases — what we've actually done with this CLI.

    This is NOT a help replacement. For command syntax use --help.
    For use cases: patterns, worked examples, when to reach for this CLI.

    If you solved a problem with ebdocs that isn't listed here, please
    capture it: run /capture-cli-use-case  or edit use-cases.yaml directly.
    Undocumented use cases are invisible to Watson and future sessions.
    """
    use_cases = _load_use_cases()

    if stale is not None:
        use_cases = _filter_stale(use_cases, stale)
        if not use_cases:
            typer.echo(f"No stale use cases (all verified within {stale} days).")
            return
    else:
        use_cases = _filter_by_tag(use_cases, tag)

    if fmt == "json":
        _render_json(use_cases)
    elif fmt == "md":
        _render_markdown(use_cases)
    else:
        _render_human(use_cases, detail_id=use_case_id)

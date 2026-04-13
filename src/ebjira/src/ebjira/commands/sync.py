"""Sync commands -- bidirectional YAML sync with Jira.

Pull issues to local YAML files (one per issue), diff local vs remote,
push only changed fields, manage snapshots.

Examples:
    ebjira sync pull --project EARL
    ebjira sync push --project EARL --dry-run
    ebjira sync diff --project EARL
    ebjira sync snapshot --project EARL
    ebjira sync diff-snapshots --project EARL --a 2026-04-06T143022 --b current
    ebjira sync list-snapshots --project EARL
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

sync_app = typer.Typer(no_args_is_help=True)


@sync_app.command()
def pull(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    jql: Annotated[Optional[str], typer.Option("--jql", help="Custom JQL (overrides project filter).")] = None,
    issue_type: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by issue type (Story, Epic, Task, Bug).")] = None,
    max_results: Annotated[int, typer.Option("--max-results", help="Max issues to pull.")] = 500,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing files.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Pull issues from Jira to local YAML files (one file per issue).

    Files are organized by type: epics/, stories/, tasks/, bugs/, subtasks/.
    Writes .pull-metadata.json with pull timestamp and JQL.

    Examples:
        ebjira sync pull --project EARL
        ebjira sync pull --project EARL --dry-run
        ebjira sync pull --project EARL --type Story
        ebjira sync pull --jql 'project = EARL AND status = "In Progress"'
    """
    from ebjira.sync_engine import pull_issues

    client = get_client()
    result = pull_issues(client, project, jql=jql, issue_type=issue_type,
                         max_results=max_results, dry_run=dry_run)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command()
def push(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    keys: Annotated[Optional[list[str]], typer.Option("--key", "-k", help="Specific issue keys to push (repeatable).")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without pushing.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Push local YAML changes to Jira (only changed fields).

    Compares each local YAML file against the live Jira state and sends
    a minimal update payload containing only the fields that differ.

    Examples:
        ebjira sync push --project EARL --dry-run
        ebjira sync push --project EARL --key EARL-10 --key EARL-11
        ebjira sync push --project EARL
    """
    from ebjira.sync_engine import push_issues

    client = get_client()
    result = push_issues(client, project, keys=keys, dry_run=dry_run)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command("diff")
def diff_cmd(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    jql: Annotated[Optional[str], typer.Option("--jql", help="Custom JQL.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Compare local YAML files against live Jira state.

    Shows which issues have local modifications, which exist only locally,
    and which exist only in Jira.

    Examples:
        ebjira sync diff --project EARL
    """
    from ebjira.sync_engine import diff_issues

    client = get_client()
    result = diff_issues(client, project, jql=jql)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command()
def snapshot(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Create a timestamped snapshot of current sync state.

    Copies all YAML files to dist/sync/{project}/snapshots/{timestamp}/.

    Examples:
        ebjira sync snapshot --project EARL
    """
    from ebjira.sync_engine import create_snapshot

    result = create_snapshot(project)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command("list-snapshots")
def list_snapshots_cmd(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """List all snapshots for a project.

    Examples:
        ebjira sync list-snapshots --project EARL
    """
    from ebjira.sync_engine import list_snapshots

    result = list_snapshots(project)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command("diff-snapshots")
def diff_snapshots_cmd(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    a: Annotated[str, typer.Option("--a", help="First snapshot timestamp (or 'current').")] = "current",
    b: Annotated[str, typer.Option("--b", help="Second snapshot timestamp (or 'current').")] = "current",
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Compare two snapshots (or 'current' for live sync state).

    Examples:
        ebjira sync diff-snapshots --project EARL --a 2026-04-06T143022 --b current
        ebjira sync diff-snapshots --project EARL --a 2026-04-01T100000 --b 2026-04-06T143022
    """
    from ebjira.sync_engine import diff_snapshots

    result = diff_snapshots(project, a, b)
    output_result(result, format=format, json_fields=json_fields)

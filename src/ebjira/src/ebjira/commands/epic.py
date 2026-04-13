"""Epic commands — list, create, update, delete epics and manage children."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.issue import IssueSummary
from ebjira.output import Format, output_result

epic_app = typer.Typer(no_args_is_help=True)


@epic_app.command()
def children(
    key: str = typer.Argument(help="Epic issue key (e.g. PROJ-42)"),
    limit: Optional[int] = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Get all child issues of an epic."""
    client = get_client()
    raw_issues = client.get_agile_paginated(
        client.agile(f"/epic/{key}/issue"),
        results_key="issues",
        max_results=limit,
    )
    issues = [IssueSummary.from_jira(i).model_dump() for i in raw_issues]
    output_result(
        issues,
        format=format,
        json_fields=json,
        columns=["key", "status", "assignee", "priority", "summary"],
    )


@epic_app.command(name="list")
def list_epics(
    project: str = typer.Option(..., "--project", "-p", help="Project key (required)."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List epics in a project."""
    client = get_client()
    jql = f"project = {project} AND issuetype = Epic ORDER BY created DESC"
    raw_issues = client.search_jql_all(
        jql=jql,
        fields=["summary", "status", "assignee", "issuetype", "priority", "labels", "created", "updated"],
        max_results=limit,
    )
    issues = [IssueSummary.from_jira(i).model_dump() for i in raw_issues]
    output_result(
        issues,
        format=format,
        json_fields=json,
        columns=["key", "status", "assignee", "summary"],
    )


@epic_app.command("create")
def create_epic(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    summary: Annotated[str, typer.Option("--summary", "-s", help="Epic summary/title.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Epic description.")] = None,
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Create a new epic.

    Example: ebjira epic create --project EARL --summary "Q2 Goals"
    """
    client = get_client()
    fields: dict = {
        "project": {"key": project},
        "issuetype": {"name": "Epic"},
        "summary": summary,
    }
    if description:
        from ebjira.commands.issue import _markdown_to_adf
        fields["description"] = _markdown_to_adf(description)
    result = client.post(client.platform("/issue"), json={"fields": fields})
    output_result(result, format=format, json_fields=json)


@epic_app.command("update")
def update_epic(
    key: Annotated[str, typer.Argument(help="Epic issue key (e.g. EARL-10).")],
    summary: Annotated[Optional[str], typer.Option("--summary", "-s", help="New summary.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New description.")] = None,
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Update an epic's fields.

    Example: ebjira epic update EARL-10 --summary "Updated Q2 Goals"
    """
    fields: dict = {}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        from ebjira.commands.issue import _markdown_to_adf
        fields["description"] = _markdown_to_adf(description)
    if not fields:
        output_result(
            {"message": "No fields to update."},
            format=format,
            json_fields=json,
        )
        return

    client = get_client()
    client.put(client.platform(f"/issue/{key}"), json={"fields": fields})
    output_result(
        {"key": key, "message": "Epic updated successfully."},
        format=format,
        json_fields=json,
    )


@epic_app.command("delete")
def delete_epic(
    key: Annotated[str, typer.Argument(help="Epic issue key (e.g. EARL-10).")],
    delete_subtasks: Annotated[bool, typer.Option("--delete-subtasks", help="Also delete subtasks.")] = False,
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Delete an epic.

    Example: ebjira epic delete EARL-10
    """
    client = get_client()
    client.delete(
        client.platform(f"/issue/{key}"),
        params={"deleteSubtasks": str(delete_subtasks).lower()},
    )
    output_result(
        {"key": key, "message": "Epic deleted."},
        format=format,
        json_fields=json,
    )


@epic_app.command("move")
def move_to_epic(
    key: Annotated[str, typer.Argument(help="Epic issue key to move issues into (e.g. EARL-10).")],
    issues: Annotated[str, typer.Option("--issues", "-i", help="Comma-separated issue keys to move (e.g. EARL-1,EARL-2).")],
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Move issues into an epic.

    Example: ebjira epic move EARL-10 --issues "EARL-1,EARL-2,EARL-3"
    """
    client = get_client()
    issue_keys = [k.strip() for k in issues.split(",") if k.strip()]
    payload = {"issues": issue_keys}
    client.post(client.agile(f"/epic/{key}/issue"), json=payload)
    output_result(
        {"epic": key, "moved": issue_keys, "message": f"Moved {len(issue_keys)} issue(s) to epic {key}."},
        format=format,
        json_fields=json,
    )

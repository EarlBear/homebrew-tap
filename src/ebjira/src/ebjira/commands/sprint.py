"""Sprint commands — list, create, update, delete sprints and manage issues."""

from __future__ import annotations

from typing import Optional

import typer

from ebjira.client import get_client
from ebjira.models.agile import SprintSummary
from ebjira.models.issue import IssueSummary
from ebjira.output import Format, output_result

sprint_app = typer.Typer(no_args_is_help=True)


@sprint_app.command(name="list")
def list_sprints(
    board: int = typer.Option(..., "--board", "-b", help="Board ID (required)."),
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter by state (active, closed, future)."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List sprints for a board."""
    client = get_client()
    params: dict = {}
    if state:
        params["state"] = state
    raw = client.get_agile_paginated(
        client.agile(f"/board/{board}/sprint"),
        params=params,
        max_results=limit,
    )
    sprints = [SprintSummary.from_jira(s).model_dump() for s in raw]
    output_result(
        sprints,
        format=format,
        json_fields=json,
        columns=["id", "name", "state", "start_date", "end_date"],
    )


@sprint_app.command()
def view(
    id: int = typer.Argument(help="Sprint ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """View sprint details."""
    client = get_client()
    raw = client.get(client.agile(f"/sprint/{id}"))
    sprint = SprintSummary.from_jira(raw).model_dump()
    output_result(sprint, format=format, json_fields=json)


@sprint_app.command()
def create(
    board: int = typer.Option(..., "--board", "-b", help="Board ID (required)."),
    name: str = typer.Option(..., "--name", "-n", help="Sprint name (required)."),
    start: Optional[str] = typer.Option(None, "--start", help="Start date (ISO format, e.g. 2026-04-01T00:00:00.000Z)."),
    end: Optional[str] = typer.Option(None, "--end", help="End date (ISO format)."),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="Sprint goal."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Create a new sprint."""
    client = get_client()
    body: dict = {"name": name, "originBoardId": board}
    if start:
        body["startDate"] = start
    if end:
        body["endDate"] = end
    if goal:
        body["goal"] = goal
    raw = client.post(client.agile("/sprint"), json=body)
    sprint = SprintSummary.from_jira(raw).model_dump()
    output_result(sprint, format=format, json_fields=json)


@sprint_app.command()
def update(
    id: int = typer.Argument(help="Sprint ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New sprint name."),
    state: Optional[str] = typer.Option(None, "--state", "-s", help="New state (active, closed, future)."),
    start: Optional[str] = typer.Option(None, "--start", help="New start date (ISO format)."),
    end: Optional[str] = typer.Option(None, "--end", help="New end date (ISO format)."),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="New sprint goal."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Update a sprint (only changed fields are sent)."""
    client = get_client()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if state is not None:
        body["state"] = state
    if start is not None:
        body["startDate"] = start
    if end is not None:
        body["endDate"] = end
    if goal is not None:
        body["goal"] = goal
    raw = client.put(client.agile(f"/sprint/{id}"), json=body)
    sprint = SprintSummary.from_jira(raw).model_dump()
    output_result(sprint, format=format, json_fields=json)


@sprint_app.command()
def delete(
    id: int = typer.Argument(help="Sprint ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Delete a sprint."""
    client = get_client()
    client.delete(client.agile(f"/sprint/{id}"))
    output_result({"deleted": True, "id": id}, format=format, json_fields=json)


@sprint_app.command()
def issues(
    id: int = typer.Argument(help="Sprint ID."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List issues in a sprint."""
    client = get_client()
    raw = client.get_agile_paginated(
        client.agile(f"/sprint/{id}/issue"),
        results_key="issues",
        max_results=limit,
    )
    items = [IssueSummary.from_jira(i).model_dump() for i in raw]
    output_result(
        items,
        format=format,
        json_fields=json,
        columns=["key", "status", "assignee", "priority", "summary"],
    )


@sprint_app.command()
def move(
    id: int = typer.Argument(help="Target sprint ID."),
    issues: str = typer.Option(..., "--issues", "-i", help="Comma-separated issue keys (e.g. PROJ-1,PROJ-2)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Move issues to a sprint."""
    client = get_client()
    issue_keys = [k.strip() for k in issues.split(",") if k.strip()]
    client.post(client.agile(f"/sprint/{id}/issue"), json={"issues": issue_keys})
    output_result(
        {"moved": True, "sprint_id": id, "issues": issue_keys},
        format=format,
        json_fields=json,
    )

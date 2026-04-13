"""Board commands — list boards, view details, browse issues, backlogs, columns, and quick filters."""

from __future__ import annotations

import json as json_mod
from typing import Annotated, Optional

import typer

from ebjira.client import JiraError, get_client
from ebjira.models.agile import BoardColumn, BoardSummary
from ebjira.models.issue import IssueSummary
from ebjira.output import Format, output_error, output_result

board_app = typer.Typer(no_args_is_help=True)


@board_app.command(name="list")
def list_boards(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project key."),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Board type (scrum or kanban)."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List all boards, optionally filtered by project or type."""
    client = get_client()
    params: dict = {}
    if project:
        params["projectKeyOrId"] = project
    if type:
        params["type"] = type
    raw = client.get_agile_paginated(
        client.agile("/board"),
        params=params,
        max_results=limit,
    )
    boards = [BoardSummary.from_jira(b).model_dump() for b in raw]
    output_result(
        boards,
        format=format,
        json_fields=json,
        columns=["id", "name", "board_type", "project_key"],
    )


@board_app.command()
def view(
    id: int = typer.Argument(help="Board ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """View board details."""
    client = get_client()
    raw = client.get(client.agile(f"/board/{id}"))
    board = BoardSummary.from_jira(raw).model_dump()
    output_result(board, format=format, json_fields=json)


@board_app.command()
def issues(
    id: int = typer.Argument(help="Board ID."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List issues on a board."""
    client = get_client()
    raw = client.get_agile_paginated(
        client.agile(f"/board/{id}/issue"),
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


@board_app.command()
def backlog(
    id: int = typer.Argument(help="Board ID."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List backlog issues for a board."""
    client = get_client()
    raw = client.get_agile_paginated(
        client.agile(f"/board/{id}/backlog"),
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


@board_app.command()
def config(
    id: int = typer.Argument(help="Board ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """View board configuration (raw JSON)."""
    client = get_client()
    raw = client.get(client.agile(f"/board/{id}/configuration"))
    output_result(raw, format=format, json_fields=json)


@board_app.command()
def columns(
    id: int = typer.Argument(help="Board ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List board column configuration with mapped statuses.

    Example: ebjira board columns 1
    """
    client = get_client()
    # Fetch board configuration
    raw = client.get(client.agile(f"/board/{id}/configuration"))
    column_config = raw.get("columnConfig", {})
    raw_columns = column_config.get("columns", [])

    # Collect all status IDs that need resolving
    status_ids: set[str] = set()
    for col in raw_columns:
        for s in col.get("statuses", []):
            status_ids.add(str(s.get("id", "")))

    # Build status ID -> name lookup
    status_map: dict[str, str] = {}
    if status_ids:
        try:
            status_data = client.get(
                client.platform("/statuses/search"),
                params={"maxResults": 200},
            )
            for s in status_data.get("values", []):
                status_map[str(s.get("id", ""))] = s.get("name", "")
        except JiraError:
            # Fallback: use IDs as names if status search fails
            pass

    # Parse into BoardColumn models
    items = []
    for col in raw_columns:
        status_names = []
        for s in col.get("statuses", []):
            sid = str(s.get("id", ""))
            status_names.append(status_map.get(sid, sid))
        bc = BoardColumn(
            name=col.get("name", ""),
            status_names=status_names,
            min_issues=col.get("min", 0) or 0,
            max_issues=col.get("max", 0) or 0,
        )
        items.append(bc.model_dump())

    # For table display, flatten status_names to a comma-separated string
    for item in items:
        item["statuses"] = ", ".join(item.pop("status_names"))

    output_result(
        items,
        format=format,
        json_fields=json,
        columns=["name", "statuses", "min_issues", "max_issues"],
    )


@board_app.command(name="set-columns")
def set_columns(
    id: int = typer.Argument(help="Board ID."),
    columns_json: str = typer.Option(..., "--columns", help="JSON string with column configuration."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Set board column configuration.

    Attempts the Agile REST API first, then the legacy GreenHopper API.
    If neither works, outputs a helpful error message.

    Example:
        ebjira board set-columns 1 --columns '{"columns": [{"name": "Prioritized", "statuses": [{"id": "10001"}]}]}'
    """
    client = get_client()
    try:
        body = json_mod.loads(columns_json)
    except json_mod.JSONDecodeError as e:
        output_error("INVALID_JSON", f"Failed to parse --columns JSON: {e}")
        return  # unreachable, output_error raises SystemExit

    # Attempt 1: Agile REST API PUT
    try:
        result = client.put(
            client.agile(f"/board/{id}/configuration"),
            json=body,
        )
        output_result(result, format=format, json_fields=json)
        return
    except JiraError as e:
        if e.status_code not in (403, 405):
            raise

    # Attempt 2: Legacy GreenHopper API
    try:
        result = client.put(
            f"/rest/greenhopper/1.0/rapidviewconfig/columns",
            json={"rapidViewId": id, **body},
        )
        output_result(result, format=format, json_fields=json)
        return
    except JiraError as e:
        if e.status_code not in (403, 404, 405):
            raise

    # Neither API worked
    output_error(
        "NOT_SUPPORTED",
        "Board column configuration is not available via REST API. "
        "Configure columns manually in the Jira board settings.",
    )


@board_app.command()
def quickfilters(
    id: Annotated[int, typer.Argument(help="Board ID.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """List quick filters on a board.

    Example: ebjira board quickfilters 34
    """
    client = get_client()
    raw = client.get(client.agile(f"/board/{id}/quickfilter"))
    filters = raw.get("values", raw) if isinstance(raw, dict) else raw
    items = []
    for f in filters if isinstance(filters, list) else []:
        items.append({
            "id": f.get("id", ""),
            "name": f.get("name", ""),
            "jql": f.get("jql", ""),
            "position": f.get("position", ""),
        })
    output_result(items, format=format, json_fields=json_fields, columns=["id", "name", "jql", "position"])


@board_app.command(name="add-quickfilter")
def add_quickfilter(
    board_id: Annotated[int, typer.Argument(help="Board ID.")],
    name: Annotated[str, typer.Option(help="Quick filter name.")],
    jql: Annotated[str, typer.Option(help="JQL query for the filter.")],
    description: Annotated[Optional[str], typer.Option(help="Filter description.")] = None,
    position: Annotated[Optional[int], typer.Option(help="Position in the filter list (0-based).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Add a quick filter to a board.

    Examples:
        ebjira board add-quickfilter 34 --name "Apps" --jql "issuetype in (Story, Feature, Bug)"
        ebjira board add-quickfilter 34 --name "AI" --jql "labels = ai-eligible"
    """
    client = get_client()
    body: dict = {"name": name, "jql": jql}
    if description:
        body["description"] = description
    if position is not None:
        body["position"] = position
    result = client.post(client.agile(f"/board/{board_id}/quickfilter"), json=body)
    output_result(result, format=format, json_fields=json_fields)

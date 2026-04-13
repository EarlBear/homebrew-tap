"""Dashboard commands — list, view, and create dashboards.

Examples:
    ebjira dashboard list
    ebjira dashboard list --name "Sprint"
    ebjira dashboard view 10001
    ebjira dashboard create --name "My Dashboard" --description "Team metrics"
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Dashboard
from ebjira.output import Format, output_result

dashboard_app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# ── Shared option defaults ──

FormatOption = Annotated[
    Format,
    typer.Option("--format", "-f", help="Output format: json, table, or plain."),
]

JsonOption = Annotated[
    Optional[str],
    typer.Option("--json", "-j", help="Comma-separated fields to include in JSON output."),
]


# ── list ──


@dashboard_app.command("list")
def list_dashboards(
    name: Annotated[Optional[str], typer.Option(help="Filter dashboards by name.")] = None,
    limit: Annotated[int, typer.Option(help="Max results to return.")] = 25,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List or search dashboards.

    Example: ebjira dashboard list --name "Sprint"
    """
    client = get_client()
    params: dict = {}
    if name:
        params["dashboardName"] = name

    raw = client.get_paginated(
        client.platform("/dashboard/search"),
        results_key="values",
        params=params,
        max_results=limit,
    )

    dashboards = [Dashboard.from_jira(d).model_dump() for d in raw]
    output_result(
        dashboards,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "owner"],
    )


# ── view ──


@dashboard_app.command("view")
def view_dashboard(
    id: Annotated[str, typer.Argument(help="Dashboard ID.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """View dashboard details.

    Example: ebjira dashboard view 10001
    """
    client = get_client()
    data = client.get(client.platform(f"/dashboard/{id}"))
    dashboard = Dashboard.from_jira(data).model_dump()
    output_result(dashboard, format=format, json_fields=json_fields)


# ── create ──


@dashboard_app.command("create")
def create_dashboard(
    name: Annotated[str, typer.Option(help="Dashboard name.")],
    description: Annotated[Optional[str], typer.Option(help="Dashboard description.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Create a new dashboard.

    Example: ebjira dashboard create --name "My Dashboard" --description "Team metrics"
    """
    client = get_client()
    body: dict = {"name": name}
    if description:
        body["description"] = description

    result = client.post(client.platform("/dashboard"), json=body)
    dashboard = Dashboard.from_jira(result).model_dump()
    output_result(dashboard, format=format, json_fields=json_fields)

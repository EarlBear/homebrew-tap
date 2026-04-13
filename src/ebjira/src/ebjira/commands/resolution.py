"""Resolution commands — list all resolutions in the Jira instance."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Resolution
from ebjira.output import Format, output_result

resolution_app = typer.Typer(
    name="resolution",
    help="View resolutions.",
    no_args_is_help=True,
)


@resolution_app.command("list")
def list_resolutions(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of resolutions to return.")] = 50,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all resolutions in the Jira instance."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/resolution/search"),
        results_key="values",
        max_results=limit,
    )
    resolutions = [Resolution.from_jira(r).model_dump() for r in raw]
    output_result(
        resolutions,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "description"],
    )

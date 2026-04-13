"""Priority commands — list all priorities in the Jira instance."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Priority
from ebjira.output import Format, output_result

priority_app = typer.Typer(
    name="priority",
    help="View priorities.",
    no_args_is_help=True,
)


@priority_app.command("list")
def list_priorities(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of priorities to return.")] = 50,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all priorities in the Jira instance."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/priority/search"),
        results_key="values",
        max_results=limit,
    )
    priorities = [Priority.from_jira(p).model_dump() for p in raw]
    output_result(
        priorities,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "description"],
    )

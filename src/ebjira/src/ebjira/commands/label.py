"""Label commands — list all labels in the Jira instance."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

label_app = typer.Typer(
    name="label",
    help="View labels.",
    no_args_is_help=True,
)


@label_app.command("list")
def list_labels(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of labels to return.")] = 50,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all labels in the Jira instance."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/label"),
        results_key="values",
        max_results=limit,
    )
    # Labels are plain strings, wrap them for consistent output
    labels = [{"name": label} for label in raw]
    output_result(
        labels,
        format=format,
        json_fields=json_fields,
        columns=["name"],
    )

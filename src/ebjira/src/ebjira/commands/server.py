"""Server info and health check commands."""

from __future__ import annotations

from typing import Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

server_app = typer.Typer(help="Server info and health check.")


@server_app.command()
def info(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Show Jira server information."""
    client = get_client()
    data = client.get(client.platform("/serverInfo"))
    output_result(data, format=format, json_fields=json_fields)


@server_app.command()
def health(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Quick connectivity check against the Jira server."""
    client = get_client()
    data = client.get(client.platform("/serverInfo"))
    result = {
        "status": "ok",
        "base_url": data.get("baseUrl", ""),
        "version": data.get("version", ""),
        "deployment_type": data.get("deploymentType", ""),
    }
    output_result(result, format=format, json_fields=json_fields)

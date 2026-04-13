"""User search and info commands."""

from __future__ import annotations

from typing import Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import UserSummary
from ebjira.output import Format, output_result

user_app = typer.Typer(help="Search and view users.")

USER_COLUMNS = ["account_id", "display_name", "email_address", "active"]


@user_app.command()
def search(
    query: str = typer.Argument(help="Name or email to search for."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Search users by name or email."""
    client = get_client()
    data = client.get(
        client.platform("/user/search"),
        params={"query": query, "maxResults": limit},
    )
    users = [UserSummary.from_jira(u).model_dump() for u in data]
    output_result(users, format=format, json_fields=json_fields, columns=USER_COLUMNS)


@user_app.command("list")
def list_users(
    limit: int = typer.Option(50, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List all users."""
    client = get_client()
    all_users: list[dict] = []
    start_at = 0
    page_size = min(limit, 50)

    while len(all_users) < limit:
        data = client.get(
            client.platform("/users/search"),
            params={"maxResults": page_size, "startAt": start_at},
        )
        if not data:
            break
        all_users.extend(data)
        if len(data) < page_size:
            break
        start_at += len(data)

    all_users = all_users[:limit]
    users = [UserSummary.from_jira(u).model_dump() for u in all_users]
    output_result(users, format=format, json_fields=json_fields, columns=USER_COLUMNS)


@user_app.command()
def me(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Show current authenticated user info."""
    client = get_client()
    data = client.get(client.platform("/myself"))
    user = UserSummary.from_jira(data).model_dump()
    output_result(user, format=format, json_fields=json_fields, columns=USER_COLUMNS)


@user_app.command()
def groups(
    account_id: str = typer.Argument(help="Jira account ID of the user."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Get groups for a user."""
    client = get_client()
    data = client.get(
        client.platform("/user/groups"),
        params={"accountId": account_id},
    )
    groups_list = [{"name": g.get("name", ""), "groupId": g.get("groupId", "")} for g in data]
    output_result(groups_list, format=format, json_fields=json_fields, columns=["name", "groupId"])

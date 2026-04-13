"""Worklog commands — list, add, and delete time tracking entries.

Examples:
    ebjira worklog list PROJ-123
    ebjira worklog add PROJ-123 --time "2h 30m"
    ebjira worklog add PROJ-123 --time "1d" --comment "Code review"
    ebjira worklog delete PROJ-123 12345
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

worklog_app = typer.Typer(
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


def _parse_worklog(data: dict) -> dict:
    """Extract relevant fields from a raw worklog entry."""
    author = data.get("author", {})
    comment = data.get("comment", {})
    # Extract plain text from ADF comment body
    comment_text = ""
    if isinstance(comment, dict):
        for block in comment.get("content", []):
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    comment_text += inline.get("text", "")
    return {
        "id": data.get("id", ""),
        "author": author.get("displayName", "") if isinstance(author, dict) else "",
        "timeSpent": data.get("timeSpent", ""),
        "started": data.get("started", ""),
        "comment": comment_text,
    }


# ── list ──


@worklog_app.command("list")
def list_worklogs(
    issue_key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List worklogs for an issue.

    Example: ebjira worklog list PROJ-123
    """
    client = get_client()
    data = client.get(client.platform(f"/issue/{issue_key}/worklog"))
    worklogs = [_parse_worklog(w) for w in data.get("worklogs", [])]
    output_result(
        worklogs,
        format=format,
        json_fields=json_fields,
        columns=["id", "author", "timeSpent", "started"],
    )


# ── add ──


@worklog_app.command("add")
def add_worklog(
    issue_key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    time: Annotated[str, typer.Option(help='Time spent (e.g. "2h", "1d 4h", "30m").')],
    started: Annotated[Optional[str], typer.Option(help="Start time as ISO datetime (defaults to now).")] = None,
    comment: Annotated[Optional[str], typer.Option(help="Worklog comment.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Add a worklog entry to an issue.

    Example: ebjira worklog add PROJ-123 --time "2h 30m" --comment "Code review"
    """
    client = get_client()
    body: dict = {
        "timeSpent": time,
        "started": started or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
    }
    if comment:
        from ebjira.commands.issue import _markdown_to_adf
        body["comment"] = _markdown_to_adf(comment)

    result = client.post(client.platform(f"/issue/{issue_key}/worklog"), json=body)
    output_result(_parse_worklog(result), format=format, json_fields=json_fields)


# ── delete ──


@worklog_app.command("delete")
def delete_worklog(
    issue_key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    worklog_id: Annotated[str, typer.Argument(help="Worklog ID to delete.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Delete a worklog entry.

    Example: ebjira worklog delete PROJ-123 12345
    """
    client = get_client()
    client.delete(client.platform(f"/issue/{issue_key}/worklog/{worklog_id}"))
    output_result(
        {"deleted": True, "id": worklog_id},
        format=format,
        json_fields=json_fields,
    )

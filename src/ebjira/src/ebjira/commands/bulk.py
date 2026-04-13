"""Bulk operations — transition or update multiple issues matching a JQL query."""

from __future__ import annotations

import sys
import time
from typing import Annotated, Optional

import typer

from ebjira.client import JiraError, get_client
from ebjira.output import Format, output_result

bulk_app = typer.Typer(
    name="bulk",
    help="Bulk operations on issues (transition, update).",
    no_args_is_help=True,
)


def _search_issues(jql: str, limit: int) -> list[dict]:
    """Search for issues matching JQL, returning key and status."""
    client = get_client()
    return client.search_jql_all(
        jql=jql,
        fields=["summary", "status", "labels", "components"],
        max_results=limit,
    )


def _print_progress(current: int, total: int, key: str, action: str) -> None:
    """Print progress to stderr."""
    print(f"  Processed {current}/{total} issues... {action} {key}", file=sys.stderr)


@bulk_app.command("transition")
def bulk_transition(
    jql: Annotated[str, typer.Option("--jql", help="JQL query to select issues.")],
    to: Annotated[str, typer.Option("--to", help="Target status name.")],
    comment: Annotated[Optional[str], typer.Option("--comment", help="Comment to add with each transition.")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max issues to process.")] = 200,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen without making changes.")] = False,
    delay_ms: Annotated[int, typer.Option("--delay-ms", help="Delay between API calls in milliseconds.")] = 100,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Transition multiple issues matching a JQL query to a new status.

    Example: ebjira bulk transition --jql "project=EARL AND status='To Do'" --to "Prioritized"
    """
    issues = _search_issues(jql, limit)
    total = len(issues)
    results: list[dict] = []
    client = get_client()

    for i, issue in enumerate(issues, 1):
        key = issue.get("key", "")
        current_status = issue.get("fields", {}).get("status", {}).get("name", "")

        if dry_run:
            results.append({
                "key": key,
                "current_status": current_status,
                "target_status": to,
                "action": "would_transition",
            })
            _print_progress(i, total, key, "[dry-run]")
            continue

        try:
            # Fetch available transitions
            data = client.get(client.platform(f"/issue/{key}/transitions"))
            transitions = data.get("transitions", [])

            # Find matching transition
            match = None
            for t in transitions:
                if t.get("name", "").lower() == to.lower():
                    match = t
                    break
                to_status = t.get("to", {})
                if to_status.get("name", "").lower() == to.lower():
                    match = t
                    break

            if not match:
                results.append({
                    "key": key,
                    "current_status": current_status,
                    "error": f"No transition to '{to}' available",
                })
                _print_progress(i, total, key, "[skipped]")
                continue

            # Build transition payload
            payload: dict = {"transition": {"id": match["id"]}}
            if comment:
                from ebjira.commands.issue import _markdown_to_adf
                payload["update"] = {
                    "comment": [
                        {
                            "add": {
                                "body": _markdown_to_adf(comment)
                            }
                        }
                    ]
                }

            client.post(client.platform(f"/issue/{key}/transitions"), json=payload)
            results.append({
                "key": key,
                "previous_status": current_status,
                "new_status": match.get("to", {}).get("name", to),
                "action": "transitioned",
            })
            _print_progress(i, total, key, "[done]")

        except JiraError as e:
            results.append({
                "key": key,
                "error": e.message,
            })
            _print_progress(i, total, key, "[error]")

        if delay_ms > 0 and i < total:
            time.sleep(delay_ms / 1000.0)

    summary = {
        "total": total,
        "dry_run": dry_run,
        "target_status": to,
        "results": results,
    }
    output_result(summary, format=format, json_fields=json_fields)


@bulk_app.command("update")
def bulk_update(
    jql: Annotated[str, typer.Option("--jql", help="JQL query to select issues.")],
    labels: Annotated[Optional[list[str]], typer.Option("--labels", help="Labels to set (repeatable).")] = None,
    component: Annotated[Optional[str], typer.Option("--component", help="Component name to set.")] = None,
    priority: Annotated[Optional[str], typer.Option("--priority", help="Priority name to set.")] = None,
    assignee: Annotated[Optional[str], typer.Option("--assignee", help="Assignee account ID to set.")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max issues to process.")] = 200,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen without making changes.")] = False,
    delay_ms: Annotated[int, typer.Option("--delay-ms", help="Delay between API calls in milliseconds.")] = 100,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update fields on multiple issues matching a JQL query.

    Example: ebjira bulk update --jql "project=EARL" --labels ai-eligible --component discovery-toolkit
    """
    # Build the fields payload
    fields: dict = {}
    if labels is not None:
        fields["labels"] = labels
    if component is not None:
        fields["components"] = [{"name": component}]
    if priority is not None:
        fields["priority"] = {"name": priority}
    if assignee is not None:
        fields["assignee"] = {"accountId": assignee}

    if not fields:
        from ebjira.output import output_error
        output_error(
            error="NO_FIELDS",
            message="Provide at least one field to update (--labels, --component, --priority, --assignee).",
        )

    issues = _search_issues(jql, limit)
    total = len(issues)
    results: list[dict] = []
    client = get_client()

    for i, issue in enumerate(issues, 1):
        key = issue.get("key", "")

        if dry_run:
            results.append({
                "key": key,
                "fields": fields,
                "action": "would_update",
            })
            _print_progress(i, total, key, "[dry-run]")
            continue

        try:
            client.put(client.platform(f"/issue/{key}"), json={"fields": fields})
            results.append({
                "key": key,
                "action": "updated",
            })
            _print_progress(i, total, key, "[done]")
        except JiraError as e:
            results.append({
                "key": key,
                "error": e.message,
            })
            _print_progress(i, total, key, "[error]")

        if delay_ms > 0 and i < total:
            time.sleep(delay_ms / 1000.0)

    summary = {
        "total": total,
        "dry_run": dry_run,
        "fields": fields,
        "results": results,
    }
    output_result(summary, format=format, json_fields=json_fields)

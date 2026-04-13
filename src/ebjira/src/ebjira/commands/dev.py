"""Dev commands — issue-aware local development workflow.

Start working on a Jira issue, create a branch, and link your commits.

    ebjira dev start EARL-42       # Create branch, transition to In Progress
    ebjira dev status              # Show current issue you're working on
    ebjira dev finish EARL-42      # Push, transition to Ready For Review
    ebjira dev list                # Show Prioritized issues ready to pick up
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

dev_app = typer.Typer(no_args_is_help=True)


def _run_git(*args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _current_branch() -> str:
    return _run_git("branch", "--show-current")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def _extract_issue_key(branch: str) -> str | None:
    """Extract EARL-XXX from a branch name."""
    match = re.search(r"(EARL-\d+)", branch, re.IGNORECASE)
    return match.group(1).upper() if match else None


@dev_app.command(name="list")
def list_ready(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.table,
) -> None:
    """List Prioritized issues ready to work on.

    Example: ebjira dev list
    """
    client = get_client()
    issues = client.search_jql_all(
        jql=f'project = {project} AND status = "Prioritized" ORDER BY priority DESC, created ASC',
        fields=["summary", "issuetype", "priority", "assignee"],
        max_results=20,
    )
    from ebjira.models.issue import IssueSummary
    rows = [IssueSummary.from_jira(i).model_dump() for i in issues]
    output_result(rows, format=format, columns=["key", "issue_type", "priority", "assignee", "summary"])


@dev_app.command()
def start(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. EARL-42).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Start working on a Jira issue.

    Creates a git branch named feature/EARL-42-summary-slug and transitions
    the issue to In Progress.

    Example: ebjira dev start EARL-42
    """
    client = get_client()

    # Fetch issue summary for branch name
    issue = client.get(client.platform(f"/issue/{key}"), params={"fields": "summary,status"})
    summary = issue.get("fields", {}).get("summary", "")
    current_status = (issue.get("fields", {}).get("status") or {}).get("name", "")
    slug = _slugify(summary)
    branch = f"feature/{key}-{slug}"

    # Create and checkout branch
    current = _current_branch()
    if current == branch:
        typer.echo(f"Already on branch {branch}")
    else:
        _run_git("checkout", "-b", branch)

    # Transition to In Progress if not already
    if current_status != "In Progress":
        try:
            transitions = client.get(client.platform(f"/issue/{key}/transitions"))
            for t in transitions.get("transitions", []):
                if (t.get("to") or {}).get("name") == "In Progress":
                    client.post(client.platform(f"/issue/{key}/transitions"), json={
                        "transition": {"id": t["id"]}
                    })
                    break
        except Exception:
            pass  # Transition may not be available

    output_result({
        "key": key,
        "branch": branch,
        "status": "In Progress",
        "summary": summary,
        "message": f"Working on {key}. Branch: {branch}",
    }, format=format)


@dev_app.command()
def status(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Show which Jira issue you're currently working on (from branch name).

    Example: ebjira dev status
    """
    branch = _current_branch()
    key = _extract_issue_key(branch)

    if not key:
        output_result({"branch": branch, "issue": None, "message": "No Jira issue detected in branch name"}, format=format)
        return

    client = get_client()
    try:
        issue = client.get(client.platform(f"/issue/{key}"), params={"fields": "summary,status,assignee,priority"})
        fields = issue.get("fields", {})
        output_result({
            "branch": branch,
            "key": key,
            "summary": fields.get("summary", ""),
            "status": (fields.get("status") or {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", ""),
            "priority": (fields.get("priority") or {}).get("name", ""),
        }, format=format)
    except Exception:
        output_result({"branch": branch, "key": key, "message": "Issue not found in Jira"}, format=format)


@dev_app.command()
def finish(
    key: Annotated[Optional[str], typer.Argument(help="Issue key (auto-detected from branch if omitted).")] = None,
    push: Annotated[bool, typer.Option("--push/--no-push", help="Push branch to remote.")] = True,
    transition: Annotated[bool, typer.Option("--transition/--no-transition", help="Transition to Ready For Review.")] = True,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Finish working on a Jira issue.

    Pushes the branch and transitions the issue to Ready For Review.

    Examples:
        ebjira dev finish              # Auto-detect issue from branch
        ebjira dev finish EARL-42      # Explicit issue key
        ebjira dev finish --no-push    # Don't push, just transition
    """
    branch = _current_branch()

    # Auto-detect issue key from branch if not provided
    if not key:
        key = _extract_issue_key(branch)
    if not key:
        output_result({"error": "Cannot detect issue key from branch. Provide it explicitly."}, format=format)
        raise typer.Exit(1)

    results: dict = {"key": key, "branch": branch}

    # Push branch
    if push:
        _run_git("push", "-u", "origin", branch)
        results["pushed"] = True

    # Transition to Ready For Review
    if transition:
        client = get_client()
        try:
            transitions = client.get(client.platform(f"/issue/{key}/transitions"))
            for t in transitions.get("transitions", []):
                if (t.get("to") or {}).get("name") == "Ready For Review":
                    client.post(client.platform(f"/issue/{key}/transitions"), json={
                        "transition": {"id": t["id"]}
                    })
                    results["status"] = "Ready For Review"
                    break
        except Exception:
            results["transition_error"] = "Could not transition to Ready For Review"

    # Add branch link to Jira (remote link + comment)
    if push:
        try:
            repo_url = _run_git("remote", "get-url", "origin").replace(".git", "")
            branch_url = f"{repo_url}/tree/{branch}"

            client = get_client()

            # Add as Jira remote link (shows as web panel on issue)
            client.post(client.platform(f"/issue/{key}/remotelink"), json={
                "object": {
                    "url": branch_url,
                    "title": f"Branch: {branch}",
                    "icon": {"url16x16": "https://github.com/favicon.ico"},
                }
            })

            # Also add as comment for paper trail
            from ebjira.commands.issue import _markdown_to_adf
            client.post(client.platform(f"/issue/{key}/comment"), json={
                "body": _markdown_to_adf(f"### Development Complete\n- **Branch:** {branch_url}\n- **Status:** Ready for review")
            })
        except Exception:
            pass

    results["message"] = f"Finished {key}. Branch pushed, issue moved to Ready For Review."
    output_result(results, format=format)


@dev_app.command()
def commit(
    message: Annotated[str, typer.Argument(help="Commit message (issue key auto-prefixed).")],
) -> None:
    """Commit with the current issue key auto-prefixed.

    Example: ebjira dev commit "Add login validation"
    → git commit -m "EARL-42: Add login validation"
    """
    branch = _current_branch()
    key = _extract_issue_key(branch)

    if key and not message.startswith(key):
        message = f"{key}: {message}"

    _run_git("commit", "-m", message)
    typer.echo(f"Committed: {message}")

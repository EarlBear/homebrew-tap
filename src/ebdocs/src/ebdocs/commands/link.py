"""Link management commands — connect docs to external systems."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

import typer

from ebdocs.output import Format, output_error, output_result

app = typer.Typer(name="link", help="Manage links between docs and external systems")


def _docs_url(doc_id: str) -> str:
    """Construct the Google Docs edit URL for a document."""
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def _find_ebjira() -> str | None:
    """Locate the ebjira wrapper script.

    Checks (in order):
    1. bin/ebjira relative to the repo root (standard location)
    2. ebjira on PATH
    """
    # Try repo-relative path: walk up from this file to find repo root
    # gdocs-cli/src/ebdocs/commands/link.py -> repo root is 5 levels up
    import pathlib

    here = pathlib.Path(__file__).resolve()
    # Walk up until we find a directory that has bin/ebjira
    candidate = here
    for _ in range(8):
        candidate = candidate.parent
        ebjira = candidate / "bin" / "ebjira"
        if ebjira.is_file():
            return str(ebjira)

    # Fallback: check PATH
    found = shutil.which("ebjira")
    if found:
        return found

    return None


@app.command("jira")
def link_jira(
    doc_id: str = typer.Argument(..., help="Document ID to link"),
    issue: str = typer.Option(
        ..., "--issue", help="Jira issue key (e.g. EARL-42)"
    ),
    comment: Optional[str] = typer.Option(
        None, "--comment", help="Optional comment text to include alongside the link"
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Link a Google Doc to a Jira issue by adding a comment with the doc URL.

    Uses the ebjira CLI to post a comment containing the Google Docs URL
    to the specified Jira issue.
    """
    url = _docs_url(doc_id)

    # Build comment body
    if comment:
        comment_body = f"{comment}\n\nGoogle Doc: {url}"
    else:
        comment_body = f"Google Doc: {url}"

    ebjira = _find_ebjira()
    if not ebjira:
        output_error(
            error="EBJIRA_NOT_FOUND",
            message=(
                "ebjira CLI not found. Ensure bin/ebjira exists at the repo root "
                "or ebjira is on PATH. Build with: make jira-cli-build"
            ),
        )

    try:
        result = subprocess.run(
            [ebjira, "issue", "comment", issue, comment_body],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        output_error(
            error="EBJIRA_TIMEOUT",
            message=f"ebjira timed out after 60s adding comment to {issue}",
        )
    except FileNotFoundError:
        output_error(
            error="EBJIRA_NOT_FOUND",
            message=f"ebjira binary not found at: {ebjira}",
        )

    if result.returncode != 0:
        stderr_msg = result.stderr.strip() if result.stderr else "unknown error"
        output_error(
            error="EBJIRA_FAILED",
            message=f"ebjira exited with code {result.returncode}: {stderr_msg}",
            status=1,
        )

    output_result(
        {
            "status": "linked",
            "issue": issue,
            "doc_id": doc_id,
            "url": url,
            "comment": comment_body,
        },
        format=format,
    )

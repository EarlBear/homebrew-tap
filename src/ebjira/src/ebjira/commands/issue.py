"""Issue commands — create, view, update, search, transition, and comment.

Examples:
    ebjira issue list --project PROJ --status "In Progress"
    ebjira issue view PROJ-123
    ebjira issue create --project PROJ --type Task --summary "Fix login bug"
    ebjira issue transition PROJ-123 "In Progress"
    ebjira issue comment PROJ-123 "Looks good, merging now"
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.issue import IssueDetail, IssueSummary, Transition
from ebjira.output import Format, output_result

issue_app = typer.Typer(
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


@issue_app.command("list")
def list_issues(
    jql: Annotated[Optional[str], typer.Option(help="Raw JQL query (overrides other filters).")] = None,
    project: Annotated[Optional[str], typer.Option(help="Filter by project key.")] = None,
    status: Annotated[Optional[str], typer.Option(help="Filter by status name.")] = None,
    type: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by issue type.")] = None,
    assignee: Annotated[Optional[str], typer.Option(help="Filter by assignee (displayName or 'currentUser').")] = None,
    label: Annotated[Optional[list[str]], typer.Option(help="Filter by label (repeatable).")] = None,
    sprint: Annotated[Optional[str], typer.Option(help="Filter by sprint name or ID.")] = None,
    limit: Annotated[int, typer.Option(help="Max results to return.")] = 25,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Search issues with JQL or filter options.

    Build JQL automatically from --project, --status, --type, --assignee,
    --label, and --sprint, or pass raw JQL with --jql.
    """
    if jql is None:
        clauses: list[str] = []
        if project:
            clauses.append(f'project = "{project}"')
        if status:
            clauses.append(f'status = "{status}"')
        if type:
            clauses.append(f'issuetype = "{type}"')
        if assignee:
            if assignee.lower() == "currentuser":
                clauses.append("assignee = currentUser()")
            else:
                clauses.append(f'assignee = "{assignee}"')
        if label:
            for lbl in label:
                clauses.append(f'labels = "{lbl}"')
        if sprint:
            clauses.append(f'sprint = "{sprint}"')
        jql = " AND ".join(clauses) if clauses else "ORDER BY updated DESC"
        if clauses:
            jql += " ORDER BY updated DESC"

    client = get_client()
    raw_issues = client.search_jql_all(
        jql=jql,
        fields=[
            "summary", "status", "assignee", "issuetype",
            "priority", "labels", "created", "updated",
        ],
        max_results=limit,
    )

    issues = [IssueSummary.from_jira(i).model_dump() for i in raw_issues]
    output_result(
        issues,
        format=format,
        json_fields=json_fields,
        columns=["key", "status", "assignee", "priority", "summary"],
    )


list_issues.__doc__ = list_issues.__doc__ or ""
issue_app.registered_commands[-1].help = (
    "Search issues with JQL or filter options."
)


# ── view ──


@issue_app.command("view")
def view_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """View full issue details including comments.

    Example: ebjira issue view PROJ-123
    """
    client = get_client()
    data = client.get(
        client.platform(f"/issue/{key}"),
        params={"expand": "renderedFields"},
    )
    detail = IssueDetail.from_jira(data).model_dump()
    output_result(detail, format=format, json_fields=json_fields)


# ── history ──


@issue_app.command("history")
def history_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Show the changelog (status transitions, assignee/label/field changes) for an issue.

    Returns a chronological list of events, each with author, timestamp, and the
    field-level changes (from/to values). Useful for reconstructing the paper trail
    of who moved an issue between columns and when.

    Example: ebjira issue history PROJ-123
    """
    client = get_client()
    data = client.get(
        client.platform(f"/issue/{key}"),
        params={"expand": "changelog"},
    )
    changelog = data.get("changelog") or {}
    histories = changelog.get("histories") or []
    events = []
    for entry in histories:
        author = entry.get("author") or {}
        items = entry.get("items") or []
        events.append(
            {
                "created": entry.get("created", ""),
                "author": author.get("displayName", "") if isinstance(author, dict) else "",
                "author_account_id": author.get("accountId", "") if isinstance(author, dict) else "",
                "changes": [
                    {
                        "field": it.get("field", ""),
                        "from": it.get("fromString", ""),
                        "to": it.get("toString", ""),
                    }
                    for it in items
                ],
            }
        )
    events.sort(key=lambda e: e["created"])
    output_result(events, format=format, json_fields=json_fields)


# ── create ──


@issue_app.command("create")
def create_issue(
    project: Annotated[str, typer.Option(help="Project key (e.g. PROJ).")],
    type: Annotated[str, typer.Option("--type", "-t", help="Issue type (e.g. Task, Bug, Story).")],
    summary: Annotated[str, typer.Option(help="Issue summary/title.")],
    description: Annotated[Optional[str], typer.Option(help="Plain-text description.")] = None,
    assignee: Annotated[Optional[str], typer.Option(help="Assignee account ID.")] = None,
    priority: Annotated[Optional[str], typer.Option(help="Priority name (e.g. High, Medium).")] = None,
    labels: Annotated[Optional[list[str]], typer.Option(help="Labels (repeatable).")] = None,
    parent: Annotated[Optional[str], typer.Option(help="Parent issue key (for subtasks or epic children).")] = None,
    fields: Annotated[Optional[str], typer.Option(help="Arbitrary fields as a JSON string.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Create a new Jira issue.

    Example: ebjira issue create --project PROJ --type Task --summary "Fix bug"
    """
    issue_fields: dict = {
        "project": {"key": project},
        "issuetype": {"name": type},
        "summary": summary,
    }

    if description:
        issue_fields["description"] = _markdown_to_adf(description)

    if assignee:
        issue_fields["assignee"] = {"accountId": assignee}

    if priority:
        issue_fields["priority"] = {"name": priority}

    if labels:
        issue_fields["labels"] = labels

    if parent:
        issue_fields["parent"] = {"key": parent}

    if fields:
        extra = json.loads(fields)
        issue_fields.update(extra)

    client = get_client()
    result = client.post(client.platform("/issue"), json={"fields": issue_fields})
    output_result(result, format=format, json_fields=json_fields)


# ── update ──


@issue_app.command("update")
def update_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    summary: Annotated[Optional[str], typer.Option(help="New summary.")] = None,
    description: Annotated[Optional[str], typer.Option(help="New description (markdown). Replaces existing unless --append.")] = None,
    append: Annotated[bool, typer.Option("--append", help="Append to existing description instead of replacing.")] = False,
    assignee: Annotated[Optional[str], typer.Option(help="Assignee account ID.")] = None,
    priority: Annotated[Optional[str], typer.Option(help="Priority name.")] = None,
    labels: Annotated[Optional[list[str]], typer.Option(help="Labels (replaces existing, repeatable).")] = None,
    fields: Annotated[Optional[str], typer.Option(help="Arbitrary fields as a JSON string.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Update an existing issue's fields.

    Examples:
        ebjira issue update PROJ-123 --summary "Updated title" --priority High
        ebjira issue update PROJ-123 --description "New content" --append
    """
    client = get_client()
    issue_fields: dict = {}

    if summary is not None:
        issue_fields["summary"] = summary

    if description is not None:
        if append:
            # Fetch existing description, extract text, append new content
            existing = client.get(client.platform(f"/issue/{key}"), params={"fields": "description"})
            existing_desc = existing.get("fields", {}).get("description")
            existing_text = ""
            if existing_desc:
                from ebjira.models.issue import _extract_adf_text
                existing_text = _extract_adf_text(existing_desc).strip()
            combined = existing_text + "\n\n" + description if existing_text else description
            issue_fields["description"] = _markdown_to_adf(combined)
        else:
            issue_fields["description"] = _markdown_to_adf(description)

    if assignee is not None:
        issue_fields["assignee"] = {"accountId": assignee}

    if priority is not None:
        issue_fields["priority"] = {"name": priority}

    if labels is not None:
        issue_fields["labels"] = labels

    if fields:
        extra = json.loads(fields)
        issue_fields.update(extra)

    if not issue_fields:
        output_result({"message": "No fields to update."}, format=format, json_fields=json_fields)
        return

    client.put(client.platform(f"/issue/{key}"), json={"fields": issue_fields})
    output_result(
        {"key": key, "message": "Issue updated successfully."},
        format=format,
        json_fields=json_fields,
    )


# ── delete ──


@issue_app.command("delete")
def delete_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    delete_subtasks: Annotated[bool, typer.Option("--delete-subtasks", help="Also delete subtasks.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Delete an issue (and optionally its subtasks).

    Example: ebjira issue delete PROJ-123 --delete-subtasks
    """
    client = get_client()
    client.delete(
        client.platform(f"/issue/{key}"),
        params={"deleteSubtasks": str(delete_subtasks).lower()},
    )
    output_result(
        {"key": key, "message": "Issue deleted."},
        format=format,
        json_fields=json_fields,
    )


# ── transition ──


@issue_app.command("transition")
def transition_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    status: Annotated[str, typer.Argument(help="Target status name or transition ID.")],
    comment: Annotated[Optional[str], typer.Option(help="Comment to add with the transition.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Transition an issue to a new status.

    Matches the target status by name (case-insensitive) or transition ID.

    Example: ebjira issue transition PROJ-123 "In Progress"
    """
    client = get_client()

    # Fetch available transitions
    data = client.get(client.platform(f"/issue/{key}/transitions"))
    transitions = data.get("transitions", [])

    # Find matching transition by name (case-insensitive) or ID
    match = None
    for t in transitions:
        if t.get("id") == status:
            match = t
            break
        if t.get("name", "").lower() == status.lower():
            match = t
            break
        # Also match on the target status name
        to_status = t.get("to", {})
        if to_status.get("name", "").lower() == status.lower():
            match = t
            break

    if not match:
        available = ", ".join(
            f'{t.get("name")} (id={t.get("id")})' for t in transitions
        )
        typer.echo(
            f'No transition matching "{status}". Available: {available}',
            err=True,
        )
        raise typer.Exit(1)

    # Build transition payload
    payload: dict = {"transition": {"id": match["id"]}}
    if comment:
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
    output_result(
        {
            "key": key,
            "transition": match.get("name", ""),
            "to": match.get("to", {}).get("name", ""),
            "message": "Transition completed.",
        },
        format=format,
        json_fields=json_fields,
    )


# ── transitions ──


@issue_app.command("transitions")
def list_transitions(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List available transitions for an issue.

    Example: ebjira issue transitions PROJ-123
    """
    client = get_client()
    data = client.get(client.platform(f"/issue/{key}/transitions"))

    transitions = []
    for t in data.get("transitions", []):
        parsed = Transition.model_validate(t)
        transitions.append({
            "id": parsed.id,
            "name": parsed.name,
            "to": parsed.to.name if parsed.to else "",
        })

    output_result(
        transitions,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "to"],
    )


# ── comment ──


@issue_app.command("comment")
def add_comment(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    body: Annotated[str, typer.Argument(help="Comment text.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Add a comment to an issue.

    Example: ebjira issue comment PROJ-123 "This is fixed in v2.1"
    """
    client = get_client()
    payload = {"body": _markdown_to_adf(body)}
    result = client.post(client.platform(f"/issue/{key}/comment"), json=payload)
    output_result(result, format=format, json_fields=json_fields)


def _markdown_to_adf(text: str) -> dict:
    """Convert simple markdown to Atlassian Document Format.

    Supports:
    - # Heading 1, ## Heading 2, ### Heading 3
    - **bold** and *italic*
    - - bullet lists (single level)
    - Plain paragraphs
    - Blank lines as paragraph breaks
    """
    import re

    content: list[dict] = []
    lines = text.split("\n")
    current_list_items: list[dict] = []

    def _flush_list() -> None:
        nonlocal current_list_items
        if current_list_items:
            content.append({"type": "bulletList", "content": current_list_items})
            current_list_items = []

    def _inline_marks(line: str) -> list[dict]:
        """Parse **bold** and *italic* into ADF inline nodes."""
        nodes: list[dict] = []
        pattern = re.compile(r"(\*\*(.+?)\*\*|\*(.+?)\*)")
        pos = 0
        for m in pattern.finditer(line):
            # Text before match
            if m.start() > pos:
                nodes.append({"type": "text", "text": line[pos : m.start()]})
            if m.group(2):  # **bold**
                nodes.append({"type": "text", "text": m.group(2), "marks": [{"type": "strong"}]})
            elif m.group(3):  # *italic*
                nodes.append({"type": "text", "text": m.group(3), "marks": [{"type": "em"}]})
            pos = m.end()
        if pos < len(line):
            nodes.append({"type": "text", "text": line[pos:]})
        if not nodes:
            nodes.append({"type": "text", "text": line})
        return nodes

    for line in lines:
        stripped = line.strip()

        # Blank line — flush list, skip
        if not stripped:
            _flush_list()
            continue

        # Headings
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            _flush_list()
            level = len(heading_match.group(1))
            content.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": _inline_marks(heading_match.group(2)),
            })
            continue

        # Bullet list items
        if stripped.startswith("- ") or stripped.startswith("* "):
            item_text = stripped[2:]
            current_list_items.append({
                "type": "listItem",
                "content": [{"type": "paragraph", "content": _inline_marks(item_text)}],
            })
            continue

        # Regular paragraph
        _flush_list()
        content.append({"type": "paragraph", "content": _inline_marks(stripped)})

    _flush_list()

    if not content:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": text}]})

    return {"type": "doc", "version": 1, "content": content}


# ── meta ──


@issue_app.command("meta")
def get_meta(
    project: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Get create metadata — issue types and required fields for a project.

    Example: ebjira issue meta PROJ
    """
    client = get_client()
    data = client.get(client.platform(f"/issue/createmeta/{project}/issuetypes"))

    issue_types = []
    for it in data.get("issueTypes", data.get("values", [])):
        issue_types.append({
            "id": it.get("id", ""),
            "name": it.get("name", ""),
            "subtask": it.get("subtask", False),
        })

    output_result(
        issue_types,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "subtask"],
    )


# ── link ──


@issue_app.command("link")
def link_issue(
    key: Annotated[str, typer.Argument(help="Source issue key (e.g. PROJ-123).")],
    target_key: Annotated[str, typer.Argument(help="Target issue key (e.g. PROJ-456).")],
    type: Annotated[str, typer.Option("--type", "-t", help='Link type name (e.g. "Blocks", "Duplicates", "Relates").')],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Link two issues together.

    Example: ebjira issue link PROJ-123 PROJ-456 --type "Blocks"
    """
    client = get_client()
    payload = {
        "type": {"name": type},
        "inwardIssue": {"key": key},
        "outwardIssue": {"key": target_key},
    }
    client.post(client.platform("/issueLink"), json=payload)
    output_result(
        {"linked": True, "source": key, "target": target_key, "type": type},
        format=format,
        json_fields=json_fields,
    )


# ── unlink ──


@issue_app.command("unlink")
def unlink_issue(
    link_id: Annotated[str, typer.Argument(help="Issue link ID to remove.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Remove an issue link.

    Example: ebjira issue unlink 10001
    """
    client = get_client()
    client.delete(client.platform(f"/issueLink/{link_id}"))
    output_result(
        {"deleted": True, "id": link_id},
        format=format,
        json_fields=json_fields,
    )


# ── watch ──


@issue_app.command("watch")
def watch_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Add yourself as a watcher on an issue.

    Example: ebjira issue watch PROJ-123
    """
    client = get_client()
    myself = client.get(client.platform("/myself"))
    account_id = myself.get("accountId", "")
    client.post(
        client.platform(f"/issue/{key}/watchers"),
        json=account_id,
    )
    output_result(
        {"watching": True, "key": key},
        format=format,
        json_fields=json_fields,
    )


# ── vote ──


@issue_app.command("vote")
def vote_issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. PROJ-123).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Vote for an issue.

    Example: ebjira issue vote PROJ-123
    """
    client = get_client()
    client.post(client.platform(f"/issue/{key}/votes"))
    output_result(
        {"voted": True, "key": key},
        format=format,
        json_fields=json_fields,
    )


# ── summarize ──


@issue_app.command("summarize")
def summarize_issue(
    key: Annotated[str, typer.Option("--key", "-k", help="Issue key (e.g. EARL-123).")],
    text: Annotated[str, typer.Option("--text", "-t", help="Summary paragraph (agent-generated).")],
    model: Annotated[str, typer.Option("--model", "-m", help="Model identifier for traceability.")] = "claude-opus-4-6",
    format: FormatOption = Format.json,
) -> None:
    """Write a local-only AI summary onto an issue YAML file.

    Computes the canonical md5(summary + "\\n" + description) hash and stores
    summary_ai = {hash, text, generated_at, model}. The CLI does not call any
    LLM — the agent supplies --text. summary_ai is never pushed to Jira.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    import yaml as _yaml

    from ebjira.sync_engine import _dump_yaml, project_dir, summary_hash

    text = text.strip()
    if not text:
        raise typer.BadParameter("--text must not be empty")

    project = key.split("-", 1)[0]
    base = project_dir(project)
    matches = list(base.rglob(f"{key}.yaml")) if base.exists() else []
    if not matches:
        raise typer.BadParameter(f"Issue YAML not found for {key} under {base}")
    filepath: Path = matches[0]

    try:
        data = _yaml.safe_load(filepath.read_text()) or {}
    except _yaml.YAMLError as e:
        raise typer.BadParameter(f"YAML parse error in {filepath}: {e}") from e
    if not isinstance(data, dict):
        raise typer.BadParameter(f"Unexpected YAML shape in {filepath}")

    h = summary_hash(data.get("summary", "") or "", data.get("description", "") or "")
    data["summary_ai"] = {
        "hash": h,
        "text": text,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
    }
    filepath.write_text(_dump_yaml(data))

    output_result(
        {"key": key, "file": str(filepath), "hash": h, "model": model},
        format=format,
    )

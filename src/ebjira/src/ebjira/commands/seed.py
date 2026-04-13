"""Seed commands — declarative issue management via hierarchical YAML.

Export all project issues to a tree-structured YAML file, edit it,
then diff/apply changes back to Jira.

Format:
  epics:
    Epic Summary [EPIC-KEY]:
      - KEY | type | component | assignee | priority | labels | summary

  NEW = create this issue. Delete a line = flagged (not auto-deleted).

Examples:
    ebjira seed export --project EARL
    ebjira seed diff --project EARL
    ebjira seed apply --project EARL
    ebjira seed validate
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

seed_app = typer.Typer(no_args_is_help=True)

SEED_FILE = os.environ.get("JIRA_SEED_FILE", "manifests/jira/issues.yaml")

# Tag prefixes for double-bracket format
# [[🎫:KEY]] [[🏷️:Type]] [[📦:component]] [[👤:assignee]] [[⬆️:Priority]] [[🔖:labels]] Summary text
TAG_MAP = {
    "🎫": "key",
    "🏷️": "type",
    "📦": "component",
    "👤": "assignee",
    "⬆️": "priority",
    "🔖": "labels",
    "📊": "status",
    "🛑": "blocked_by",
    "🔗": "relates_to",
    # Short aliases still work for manual editing
    "t": "type",
    "c": "component",
    "a": "assignee",
    "p": "priority",
    "l": "labels",
    "s": "status",
}
TAG_REVERSE = {"key": "🎫", "type": "🏷️", "component": "📦", "assignee": "👤",
               "priority": "⬆️", "labels": "🔖", "status": "📊",
               "blocked_by": "🛑", "relates_to": "🔗"}


def _format_row(row: dict) -> str:
    """Format a single issue as double-bracket tagged string.

    Example: [[🎫:EARL-93]] [[t:Task]] [[c:discovery-toolkit]] [[a:omar]] [[p:Highest]] Summary text
    """
    parts = []
    parts.append(f"[[🎫:{row.get('key', '')}]]")
    parts.append(f"[[🏷️:{row.get('type', '')}]]")
    if row.get("component"):
        parts.append(f"[[📦:{row['component']}]]")
    if row.get("assignee"):
        parts.append(f"[[👤:{row['assignee']}]]")
    if row.get("priority"):
        parts.append(f"[[⬆️:{row['priority']}]]")
    if row.get("labels"):
        parts.append(f"[[🔖:{row['labels']}]]")
    # Show status only when it differs from "Prioritized" (the default)
    status = row.get("status", "")
    if status and status != "Prioritized":
        parts.append(f"[[📊:{status}]]")
    if row.get("blocked_by"):
        parts.append(f"[[🛑:{row['blocked_by']}]]")
    if row.get("relates_to"):
        parts.append(f"[[🔗:{row['relates_to']}]]")
    parts.append(row.get("summary", ""))
    return " ".join(parts)


def _parse_row(line: str) -> dict | None:
    """Parse a double-bracket tagged line back to a dict.

    Extracts [[prefix:value]] tags, remainder is summary.
    """
    row: dict = {"key": "", "type": "", "component": "", "assignee": "",
                 "priority": "", "labels": "", "status": "", "summary": ""}

    # Extract all [[prefix:value]] tags
    remainder = line
    for match in re.finditer(r"\[\[([^:]+):([^\]]*)\]\]", line):
        prefix = match.group(1)
        value = match.group(2).strip()
        field = TAG_MAP.get(prefix)
        if field:
            row[field] = value
        remainder = remainder.replace(match.group(0), "")

    # Whatever's left (stripped) is the summary
    row["summary"] = remainder.strip()

    # Must have at least a key to be valid
    if not row["key"]:
        return None
    return row


def _export_tree(project: str) -> str:
    """Pull all issues from Jira and format as hierarchical YAML."""
    client = get_client()

    issues = client.search_jql_all(
        jql=f"project = {project} ORDER BY issuetype DESC, key ASC",
        fields=["summary", "issuetype", "status", "priority", "assignee",
                "components", "labels", "parent", "issuelinks"],
        max_results=500,
    )

    # Separate epics and children
    epics: list[dict] = []
    children: dict[str, list[dict]] = {}
    orphans: list[dict] = []

    for issue in issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        parent = fields.get("parent", {})
        parent_key = parent.get("key", "") if parent else ""

        # Extract links by type
        blocked_by: list[str] = []
        relates_to: list[str] = []
        for link in (fields.get("issuelinks") or []):
            link_type = (link.get("type") or {}).get("name", "")
            if link_type == "Blocks" and "inwardIssue" in link:
                blocked_by.append(link["inwardIssue"].get("key", ""))
            elif link_type == "Relates" and "outwardIssue" in link:
                relates_to.append(link["outwardIssue"].get("key", ""))
            elif link_type == "Relates" and "inwardIssue" in link:
                relates_to.append(link["inwardIssue"].get("key", ""))

        status = (fields.get("status") or {}).get("name", "")

        row = {
            "key": key,
            "type": issue_type,
            "component": ", ".join(c.get("name", "") for c in (fields.get("components") or [])),
            "assignee": _short_name(fields.get("assignee")),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "labels": ",".join(fields.get("labels") or []),
            "status": status,
            "blocked_by": ",".join(blocked_by),
            "relates_to": ",".join(relates_to),
            "parent": (fields.get("parent") or {}).get("key", ""),
            "summary": fields.get("summary", ""),
        }

        if issue_type == "Epic":
            epics.append(row)
            if key not in children:
                children[key] = []
        elif parent_key:
            children.setdefault(parent_key, []).append(row)
        else:
            orphans.append(row)

    epics.sort(key=lambda e: e["key"])

    # Build YAML
    lines: list[str] = []
    lines.append("# Seed file for EARL project")
    lines.append("# Edit inline, then: ebjira seed diff / ebjira seed apply")
    lines.append("# Format: [[🎫:KEY]] [[🏷️:Type]] [[📦:component]] [[👤:assignee]] [[⬆️:Priority]] [[🔖:labels]] [[🛑:blocked-by]] [[🔗:relates-to]] Summary")
    lines.append("# NEW = create issue. Omit optional tags to skip fields.")
    lines.append("")
    lines.append("epics:")

    for epic in epics:
        epic_children = children.get(epic["key"], [])
        epic_children.sort(key=lambda c: c["key"])

        lines.append(f'  {epic["summary"]} [[🎫:{epic["key"]}]]:')
        if not epic_children:
            lines.append("    []")
        else:
            for child in epic_children:
                lines.append(f"    - {_format_row(child)}")

    if orphans:
        lines.append("")
        lines.append("  (no epic):")
        for orphan in orphans:
            lines.append(f"    - {_format_row(orphan)}")

    return "\n".join(lines) + "\n"


def _short_name(assignee: dict | None) -> str:
    """Convert assignee to short name (omar, duke, mazen)."""
    if not assignee:
        return ""
    name = assignee.get("displayName", "")
    # Known aliases
    aliases = {"Omar Eid": "omar"}
    return aliases.get(name, name.lower().split()[0] if name else "")


def _parse_seed(filepath: str) -> tuple[list[dict], list[dict]]:
    """Parse hierarchical YAML seed file.

    Returns: (epics, issues) where each issue has a 'parent' field.
    """
    path = Path(filepath)
    if not path.is_file():
        return [], []

    text = path.read_text()
    epics: list[dict] = []
    issues: list[dict] = []
    current_epic_key: str | None = None
    current_epic_summary: str = ""

    current_issue: dict | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Skip comments, blank lines, yaml structural
        if not stripped or stripped.startswith("#") or stripped == "epics:" or stripped == "[]":
            continue

        # Description tag: [[📝:text]] — append to current issue's description
        desc_match = re.match(r"^\[\[📝:(.+?)\]\]$", stripped)
        if desc_match and current_issue is not None:
            desc_line = desc_match.group(1)
            current_issue.setdefault("description", "")
            current_issue["description"] += desc_line + "\n"
            continue

        # AC tag: [[✅:text]] — append to current issue's acceptance criteria
        ac_match = re.match(r"^\[\[✅:(.+?)\]\]$", stripped)
        if ac_match and current_issue is not None:
            current_issue.setdefault("acceptance_criteria", "")
            current_issue["acceptance_criteria"] += ac_match.group(1) + "\n"
            continue

        # Sub-bullet under description/AC (starts with - but not a YAML list item with [[🎫:]])
        if stripped.startswith("- ") and "[[🎫:" not in stripped and current_issue is not None:
            # Append to description as a bullet
            current_issue.setdefault("description", "")
            current_issue["description"] += stripped + "\n"
            continue

        # Epic header: "  Summary [[🎫:KEY]]:" or "  Summary [KEY]:" (legacy)
        epic_match = re.match(r"^\s*(.+?)\s*\[\[🎫:(\w+(?:-\d+)?)\]\]\s*:\s*$", stripped)
        if not epic_match:
            # Legacy format without emoji
            epic_match = re.match(r"^\s*(.+?)\s*\[(\w+(?:-\d+)?)\]\s*:\s*$", stripped)
        if epic_match:
            current_epic_summary = epic_match.group(1)
            current_epic_key = epic_match.group(2)
            epics.append({"key": current_epic_key, "summary": current_epic_summary, "type": "Epic"})
            continue

        # Orphan header
        if stripped == "(no epic):":
            current_epic_key = None
            continue

        # Issue line: "    - [[🎫:KEY]] ..."
        issue_match = re.match(r"^\s*-\s*(.+)$", stripped)
        if issue_match and "[[🎫:" in issue_match.group(1):
            row = _parse_row(issue_match.group(1))
            if row:
                row["parent"] = current_epic_key
                issues.append(row)
                current_issue = row  # Track for subsequent 📝/✅ lines

    return epics, issues


def _replace_new_in_seed(filepath: str, summary: str, new_key: str) -> None:
    """Replace the first [[🎫:NEW]] line matching a summary with the real key.

    Updates the seed file in-place so you don't have to re-export after apply.
    """
    path = Path(filepath)
    if not path.is_file():
        return

    text = path.read_text()
    lines = text.split("\n")
    updated = False

    for i, line in enumerate(lines):
        # Match lines with [[🎫:NEW]] (or short alias [[t:NEW]]) that contain this summary
        if ("[[🎫:NEW]]" in line or "[[🎫:NEW " in line) and summary in line:
            lines[i] = line.replace("[[🎫:NEW]]", f"[[🎫:{new_key}]]")
            updated = True
            break  # Only replace the first match

    if updated:
        path.write_text("\n".join(lines))


def _clean_synced_issue(filepath: str, key: str) -> None:
    """Remove [[📝:...]], [[✅:...]], and sub-bullet lines for a synced issue.

    After description/AC are pushed to Jira, the YAML doesn't need to carry them.
    Only cleans lines that follow the issue's [[🎫:KEY]] line until the next issue or epic.
    """
    path = Path(filepath)
    if not path.is_file():
        return

    lines = path.read_text().split("\n")
    new_lines: list[str] = []
    found_issue = False
    cleaning = False

    for line in lines:
        stripped = line.strip()

        # Found our issue — start cleaning after this line
        if f"[[🎫:{key}]]" in line:
            found_issue = True
            cleaning = True
            new_lines.append(line)
            continue

        if cleaning:
            # Stop cleaning at next issue, epic header, or blank line before next section
            if stripped.startswith("- [[🎫:") or "[[🎫:" in stripped and stripped.endswith("]:"):
                cleaning = False
                new_lines.append(line)
                continue
            # Skip description, AC, and sub-bullet lines
            if stripped.startswith("[[📝:") or stripped.startswith("[[✅:"):
                continue
            if stripped.startswith("- ") and "[[🎫:" not in stripped:
                continue
            # Blank line — keep it, stop cleaning
            if not stripped:
                cleaning = False
                new_lines.append(line)
                continue
            # Something else — stop cleaning, keep line
            cleaning = False
            new_lines.append(line)
            continue

        new_lines.append(line)

    if found_issue:
        path.write_text("\n".join(new_lines))


def _create_links(client: Any, issue_key: str, links_str: str, link_type: str = "Blocks") -> None:
    """Create issue links. links_str is comma-separated keys.

    For Blocks: target_key blocks issue_key (target is inward, issue is outward)
    For Relates: issue_key relates to target_key
    """
    if not links_str:
        return
    for target_key in links_str.split(","):
        target_key = target_key.strip()
        if target_key:
            try:
                if link_type == "Blocks":
                    # 🛑 blocked_by: target blocks this issue
                    payload = {
                        "type": {"name": "Blocks"},
                        "inwardIssue": {"key": target_key},
                        "outwardIssue": {"key": issue_key},
                    }
                else:
                    # 🔗 relates_to: this issue relates to target
                    payload = {
                        "type": {"name": "Relates"},
                        "inwardIssue": {"key": issue_key},
                        "outwardIssue": {"key": target_key},
                    }
                client.post(client.platform("/issueLink"), json=payload)
            except Exception:
                pass  # Link may already exist


def _transition_issue(client: Any, key: str, target_status: str) -> None:
    """Transition an issue to a target status by name."""
    try:
        # Get available transitions
        data = client.get(client.platform(f"/issue/{key}/transitions"))
        transitions = data.get("transitions", [])

        # Find matching transition by target status name
        for t in transitions:
            to_status = (t.get("to") or {}).get("name", "")
            if to_status.lower() == target_status.lower():
                client.post(client.platform(f"/issue/{key}/transitions"), json={
                    "transition": {"id": t["id"]}
                })
                return

        # Also try matching by transition name
        for t in transitions:
            if t.get("name", "").lower() == target_status.lower():
                client.post(client.platform(f"/issue/{key}/transitions"), json={
                    "transition": {"id": t["id"]}
                })
                return
    except Exception:
        pass  # Transition may not be available


def _replace_epic_in_seed(filepath: str, summary: str, new_key: str) -> None:
    """Replace [NEW] in an epic header with the real key.

    Updates: '  Tech Designs [NEW]:' → '  Tech Designs [EARL-127]:'
    """
    path = Path(filepath)
    if not path.is_file():
        return

    text = path.read_text()
    # Match emoji format first, then legacy
    old_emoji = f"{summary} [[🎫:NEW]]:"
    new_emoji = f"{summary} [[🎫:{new_key}]]:"
    if old_emoji in text:
        path.write_text(text.replace(old_emoji, new_emoji, 1))
        return
    old_legacy = f"{summary} [NEW]:"
    new_legacy = f"{summary} [{new_key}]:"
    if old_legacy in text:
        path.write_text(text.replace(old_legacy, new_legacy, 1))


@seed_app.command()
def export(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Export all project issues as a hierarchical seed file.

    Examples:
        ebjira seed export --project EARL
        ebjira seed export --project EARL --output seed.yaml
    """
    tree = _export_tree(project)
    filepath = output or SEED_FILE

    Path(filepath).write_text(tree)
    issue_count = tree.count("\n    - ")

    output_result(
        {"status": "exported", "file": filepath, "issues": issue_count},
        format=format,
    )
    typer.echo(tree)


@seed_app.command()
def diff(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    seed_file: Annotated[str, typer.Option("--file", help="Seed file path.")] = SEED_FILE,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Compare seed file against live Jira issues.

    Examples:
        ebjira seed diff --project EARL
    """
    epics, seed_issues = _parse_seed(seed_file)
    if not seed_issues and not epics:
        output_result({"error": "No issues found in seed file", "file": seed_file}, format=format)
        return

    # Get live issues
    client = get_client()
    live_issues = client.search_jql_all(
        jql=f"project = {project} ORDER BY key ASC",
        fields=["summary", "issuetype", "status", "priority", "assignee",
                "components", "labels", "parent"],
        max_results=500,
    )

    live_map: dict[str, dict] = {}
    for issue in live_issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        live_map[key] = {
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "component": ", ".join(c.get("name", "") for c in (fields.get("components") or [])),
            "assignee": _short_name(fields.get("assignee")),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "labels": ",".join(fields.get("labels") or []),
            "summary": fields.get("summary", ""),
        }

    changes: list[dict] = []
    seed_keys: set[str] = set()

    # Check epics
    for epic in epics:
        seed_keys.add(epic["key"])

    # Check issues
    for row in seed_issues:
        key = row["key"]

        if key == "NEW" or key.startswith("NEW"):
            changes.append({
                "action": "create",
                "type": row["type"],
                "parent": row.get("parent", ""),
                "summary": row["summary"],
            })
            continue

        seed_keys.add(key)
        live = live_map.get(key)
        if not live:
            changes.append({"action": "missing_in_jira", "key": key, "summary": row["summary"]})
            continue

        for field in ["type", "component", "assignee", "priority", "labels", "summary"]:
            seed_val = row.get(field, "").strip()
            live_val = live.get(field, "").strip()
            if seed_val and seed_val != live_val:
                changes.append({"action": "update", "key": key, "field": field, "from": live_val, "to": seed_val})

    # Missing from seed
    for key, live in live_map.items():
        if key not in seed_keys and live["type"] != "Epic":
            changes.append({"action": "missing_in_seed", "key": key, "summary": live["summary"]})

    output_result({"changes": changes, "total": len(changes)}, format=format, json_fields=json_fields)


@seed_app.command()
def apply(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    seed_file: Annotated[str, typer.Option("--file", help="Seed file path.")] = SEED_FILE,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Apply seed file changes to Jira.

    Examples:
        ebjira seed apply --project EARL --dry-run
        ebjira seed apply --project EARL --yes
    """
    epics, seed_issues = _parse_seed(seed_file)
    if not seed_issues and not epics:
        output_result({"error": "No issues in seed file"}, format=format)
        return

    client = get_client()

    results: list[dict] = []

    # Phase 1: Create NEW epics first so children can reference them
    epic_key_map: dict[str, str] = {}  # "NEW" temp key -> real key
    for epic in epics:
        if epic["key"] == "NEW" or epic["key"].startswith("NEW"):
            if dry_run:
                results.append({"action": "would_create_epic", "summary": epic["summary"]})
                epic_key_map[epic["key"]] = "NEW-EPIC"
                continue

            epic_fields: dict = {
                "project": {"key": project},
                "issuetype": {"name": "Epic"},
                "summary": epic["summary"],
            }
            result = client.post(client.platform("/issue"), json={"fields": epic_fields})
            new_key = result.get("key", "")
            results.append({"action": "created_epic", "key": new_key, "summary": epic["summary"]})
            epic_key_map[epic["key"]] = new_key

            # Update seed file: replace [NEW] with [REAL-KEY] in epic header
            if new_key:
                _replace_epic_in_seed(seed_file, epic["summary"], new_key)

    # Remap children's parent keys
    for issue in seed_issues:
        if issue.get("parent") in epic_key_map:
            issue["parent"] = epic_key_map[issue["parent"]]

    # Phase 2: Process child issues
    live_issues = client.search_jql_all(
        jql=f"project = {project} ORDER BY key ASC",
        fields=["summary", "issuetype", "priority", "assignee", "components", "labels", "issuelinks", "parent"],
        max_results=500,
    )
    live_map = {}
    for issue in live_issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        blocked_by: list[str] = []
        relates_to: list[str] = []
        for link in (fields.get("issuelinks") or []):
            lt = (link.get("type") or {}).get("name", "")
            if lt == "Blocks" and "inwardIssue" in link:
                blocked_by.append(link["inwardIssue"].get("key", ""))
            elif lt == "Relates":
                rel_key = (link.get("outwardIssue") or link.get("inwardIssue") or {}).get("key", "")
                if rel_key:
                    relates_to.append(rel_key)
        live_map[key] = {
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "component": ", ".join(c.get("name", "") for c in (fields.get("components") or [])),
            "assignee": _short_name(fields.get("assignee")),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "labels": ",".join(fields.get("labels") or []),
            "status": (fields.get("status") or {}).get("name", ""),
            "blocked_by": ",".join(blocked_by),
            "relates_to": ",".join(relates_to),
            "parent": (fields.get("parent") or {}).get("key", ""),
            "summary": fields.get("summary", ""),
        }

    results: list[dict] = []

    for row in seed_issues:
        key = row["key"]

        if key == "NEW" or key.startswith("NEW"):
            if dry_run:
                results.append({"action": "would_create", "summary": row["summary"], "type": row["type"]})
                continue

            fields: dict = {
                "project": {"key": project},
                "issuetype": {"name": row["type"]},
                "summary": row["summary"],
            }
            if row.get("priority"):
                fields["priority"] = {"name": row["priority"]}
            if row.get("component"):
                fields["components"] = [{"name": c.strip()} for c in row["component"].split(",")]
            if row.get("labels"):
                fields["labels"] = [l.strip() for l in row["labels"].split(",") if l.strip()]
            if row.get("parent"):
                fields["parent"] = {"key": row["parent"]}

            result = client.post(client.platform("/issue"), json={"fields": fields})
            new_key = result.get("key", "")
            results.append({"action": "created", "key": new_key, "summary": row["summary"]})

            # Auto-update seed file: replace the first [[🎫:NEW]] matching this summary
            if new_key:
                _replace_new_in_seed(seed_file, row["summary"], new_key)

                # Push description + AC to Jira if present, then clean from YAML
                desc = row.get("description", "").strip()
                ac = row.get("acceptance_criteria", "").strip()
                if desc or ac:
                    full_desc = ""
                    if desc:
                        full_desc += desc
                    if ac:
                        full_desc += "\n\n### Acceptance Criteria\n" + ac
                    if full_desc:
                        from ebjira.commands.issue import _markdown_to_adf
                        client.put(client.platform(f"/issue/{new_key}"), json={
                            "fields": {"description": _markdown_to_adf(full_desc)}
                        })
                    # Clean 📝/✅ lines from YAML — description now lives in Jira
                    _clean_synced_issue(seed_file, new_key)

                # Create issue links if present
                # Create links from seed tags
                _create_links(client, new_key, row.get("blocked_by", ""), link_type="Blocks")
                _create_links(client, new_key, row.get("relates_to", ""), link_type="Relates")
            continue

        live = live_map.get(key)
        if not live:
            results.append({"action": "skipped", "key": key, "reason": "not in Jira"})
            continue

        update_fields: dict = {}
        if row["type"] and row["type"] != live["type"]:
            update_fields["issuetype"] = {"name": row["type"]}
        if row["priority"] and row["priority"] != live["priority"]:
            update_fields["priority"] = {"name": row["priority"]}
        if row["summary"] and row["summary"] != live["summary"]:
            update_fields["summary"] = row["summary"]
        if row["component"] and row["component"] != live["component"]:
            update_fields["components"] = [{"name": c.strip()} for c in row["component"].split(",")]
        if row["labels"] and row["labels"] != live["labels"]:
            update_fields["labels"] = [l.strip() for l in row["labels"].split(",") if l.strip()]

        # Re-parent if the issue moved to a different epic in the YAML
        seed_parent = row.get("parent", "")
        live_parent = live.get("parent", "")
        if seed_parent and seed_parent != live_parent:
            update_fields["parent"] = {"key": seed_parent}

        # Detect status change (requires transition, not field update)
        # No [[📊:...]] tag = leave status as-is (don't touch)
        seed_status = row.get("status", "").strip()
        live_status = live.get("status", "").strip()
        needs_transition = seed_status and seed_status != live_status

        # Check for new links to create (compare seed vs live for both link types)
        seed_blocked = set(l.strip() for l in row.get("blocked_by", "").split(",") if l.strip())
        live_blocked = set(l.strip() for l in live.get("blocked_by", "").split(",") if l.strip())
        new_blocked = seed_blocked - live_blocked

        seed_relates = set(l.strip() for l in row.get("relates_to", "").split(",") if l.strip())
        live_relates = set(l.strip() for l in live.get("relates_to", "").split(",") if l.strip())
        new_relates = seed_relates - live_relates

        new_links = new_blocked or new_relates

        if not update_fields and not new_links and not needs_transition:
            continue

        if dry_run:
            fields_changed = list(update_fields.keys())
            if new_links:
                fields_changed.append(f"links(+{','.join(new_blocked | new_relates)})")
            if needs_transition:
                fields_changed.append(f"status({live_status}→{seed_status})")
            results.append({"action": "would_update", "key": key, "fields": fields_changed})
            continue

        if update_fields:
            client.put(client.platform(f"/issue/{key}"), json={"fields": update_fields})
        if new_blocked:
            _create_links(client, key, ",".join(new_blocked), link_type="Blocks")
        if new_relates:
            _create_links(client, key, ",".join(new_relates), link_type="Relates")
        if needs_transition:
            _transition_issue(client, key, seed_status)
        changed = list(update_fields.keys())
        if new_blocked:
            changed.append("blocked_by")
        if new_relates:
            changed.append("relates_to")
        if needs_transition:
            changed.append(f"status→{seed_status}")
        results.append({"action": "updated", "key": key, "fields": changed})

    output_result({"results": results, "total": len(results)}, format=format)


@seed_app.command()
def validate(
    seed_file: Annotated[str, typer.Option("--file", help="Seed file path.")] = SEED_FILE,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Validate a seed file for consistency.

    Examples:
        ebjira seed validate
    """
    epics, issues = _parse_seed(seed_file)
    valid_types = {"Epic", "Story", "Feature", "Deliverable", "Task", "Bug", "Sub-task"}
    valid_priorities = {"Highest", "High", "Medium", "Low", "Lowest", ""}
    errors: list[dict] = []
    keys_seen: set[str] = set()
    epic_keys = {e["key"] for e in epics}

    for row in issues:
        key = row["key"]
        if key != "NEW" and key in keys_seen:
            errors.append({"key": key, "error": "Duplicate key"})
        keys_seen.add(key)

        if row["type"] not in valid_types:
            errors.append({"key": key, "error": f"Invalid type: {row['type']}"})
        if row["priority"] not in valid_priorities:
            errors.append({"key": key, "error": f"Invalid priority: {row['priority']}"})
        if key in ("NEW",) and not row["summary"]:
            errors.append({"key": key, "error": "NEW issue missing summary"})
        if row.get("parent") and row["parent"] not in epic_keys:
            errors.append({"key": key, "error": f"Parent {row['parent']} not an epic in this file"})

    output_result(
        {"valid": len(errors) == 0, "errors": errors, "issues": len(issues), "epics": len(epics)},
        format=format,
    )

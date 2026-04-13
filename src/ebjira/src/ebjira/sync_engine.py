"""Sync engine -- pull/push/diff/snapshot logic for local YAML <-> Jira sync.

One YAML file per issue, organized by type directory.
Standard YAML format (no emoji tags).

Output directory is configurable via JIRA_SYNC_DIR env var.
Default: dist/sync (relative to cwd).
Set to an absolute path to write to a separate repo, e.g.:
    JIRA_SYNC_DIR=/path/to/earlbear-content/jira
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def summary_hash(summary: str, description: str) -> str:
    """Canonical md5 hash of summary + description, used for summary_ai freshness.

    DO NOT change inputs without invalidating every existing summary_ai entry.
    """
    return hashlib.md5(((summary or "") + "\n" + (description or "")).encode("utf-8")).hexdigest()

from ebjira.client import JiraClient

# -- Constants --

def _resolve_sync_base() -> Path:
    """Resolve the sync base directory.

    Precedence:
    1. JIRA_SYNC_DIR (explicit override)
    2. CONTENT_DIR/jira (shared content repo)
    3. dist/sync (default for local dev)
    """
    explicit = os.environ.get("JIRA_SYNC_DIR")
    if explicit:
        return Path(explicit)
    content_dir = os.environ.get("CONTENT_DIR")
    if content_dir:
        return Path(content_dir) / "jira"
    return Path("dist/sync")


SYNC_BASE = _resolve_sync_base()

TYPE_DIR_MAP: dict[str, str] = {
    "Epic": "epics",
    "Story": "stories",
    "Task": "tasks",
    "Bug": "bugs",
    "Sub-task": "subtasks",
    "Feature": "stories",
    "Deliverable": "stories",
}

DEFAULT_TYPE_DIR = "tasks"

PULL_FIELDS = [
    "summary", "issuetype", "status", "priority", "assignee",
    "components", "labels", "parent", "description", "issuelinks",
    "comment", "attachment", "created", "updated",
]

DIFFABLE_FIELDS = [
    "summary", "type", "status", "priority", "assignee",
    "components", "labels", "parent", "description",
]

METADATA_FILE = ".pull-metadata.json"

# Fixed field order for deterministic YAML output (clean git diffs).
FIELD_ORDER = [
    "key", "link", "summary", "type", "status", "priority", "assignee",
    "components", "labels", "parent", "description",
    "summary_ai",
    "blocked_by", "relates_to",
    "comments", "attachments",
    "created", "updated",
]


# -- YAML helpers --

def _ordered_issue_dict(d: dict) -> dict:
    """Return a dict with keys in FIELD_ORDER, then any extras alphabetically."""
    ordered: dict[str, Any] = {}
    for field in FIELD_ORDER:
        if field in d:
            ordered[field] = d[field]
    for field in sorted(d.keys()):
        if field not in ordered:
            ordered[field] = d[field]
    return ordered


def _dump_yaml(data: dict) -> str:
    """Dump an issue dict to YAML with consistent field ordering."""
    ordered = _ordered_issue_dict(data)
    return yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)


# -- YAML issue schema --

def _get_browse_url() -> str:
    """Return the Jira browse URL prefix (e.g. https://earlbear.atlassian.net/browse/)."""
    base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    return f"{base}/browse/" if base else ""


def issue_to_yaml_dict(issue: dict) -> dict:
    """Convert a raw Jira API issue to the standard YAML dict format."""
    fields = issue.get("fields", {})
    key = issue.get("key", "")
    browse_url = _get_browse_url()

    result: dict[str, Any] = {
        "key": key,
        "link": f"{browse_url}{key}" if browse_url else "",
        "summary": fields.get("summary", ""),
        "type": (fields.get("issuetype") or {}).get("name", ""),
        "status": (fields.get("status") or {}).get("name", ""),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "assignee": _extract_assignee(fields.get("assignee")),
        "components": [c.get("name", "") for c in (fields.get("components") or [])],
        "labels": fields.get("labels") or [],
        "parent": (fields.get("parent") or {}).get("key", ""),
        "description": _extract_description(fields.get("description")),
    }

    # Extract links
    blocked_by: list[str] = []
    relates_to: list[str] = []
    for link in (fields.get("issuelinks") or []):
        link_type = (link.get("type") or {}).get("name", "")
        if link_type == "Blocks" and "inwardIssue" in link:
            blocked_by.append(link["inwardIssue"].get("key", ""))
        elif link_type == "Relates":
            rel_key = (link.get("outwardIssue") or link.get("inwardIssue") or {}).get("key", "")
            if rel_key:
                relates_to.append(rel_key)

    if blocked_by:
        result["blocked_by"] = sorted(blocked_by)
    if relates_to:
        result["relates_to"] = sorted(relates_to)

    # Extract comments
    comments_data = fields.get("comment", {})
    raw_comments = comments_data.get("comments", []) if isinstance(comments_data, dict) else []
    if raw_comments:
        comments = [
            {
                "author": (c.get("author") or {}).get("displayName", ""),
                "created": c.get("created", ""),
                "body": _extract_comment_body(c.get("body")),
            }
            for c in raw_comments
        ]
        result["comments"] = sorted(comments, key=lambda c: c["created"])

    # Extract attachments
    raw_attachments = fields.get("attachment") or []
    if raw_attachments:
        attachments = [
            {
                "filename": a.get("filename", ""),
                "size": a.get("size", 0),
                "author": (a.get("author") or {}).get("displayName", ""),
                "created": a.get("created", ""),
                "url": a.get("content", ""),
            }
            for a in raw_attachments
        ]
        result["attachments"] = sorted(attachments, key=lambda a: a["created"])

    result["created"] = fields.get("created", "")
    result["updated"] = fields.get("updated", "")

    return result


def _extract_assignee(assignee: dict | None) -> str:
    if not assignee:
        return ""
    return assignee.get("displayName", "")


def _extract_comment_body(body: Any) -> str:
    """Extract plain text from a comment body (ADF or string)."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        from ebjira.models.issue import _extract_adf_text
        return _extract_adf_text(body).strip()
    return str(body)


def _extract_description(desc: Any) -> str:
    if desc is None:
        return ""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        from ebjira.models.issue import _extract_adf_text
        return _extract_adf_text(desc).strip()
    return str(desc)


def type_dir(issue_type: str) -> str:
    """Map an issue type name to a directory name."""
    return TYPE_DIR_MAP.get(issue_type, DEFAULT_TYPE_DIR)


def project_dir(project: str) -> Path:
    """Return the sync directory for a project."""
    return SYNC_BASE / project


# -- Pull --

def pull_issues(
    client: JiraClient,
    project: str,
    jql: str | None = None,
    issue_type: str | None = None,
    max_results: int = 500,
    dry_run: bool = False,
) -> dict:
    """Pull issues from Jira and write individual YAML files.

    Returns a summary dict with counts and file paths.
    """
    if jql:
        effective_jql = jql
    elif issue_type:
        effective_jql = f"project = {project} AND issuetype = '{issue_type}' ORDER BY key ASC"
    else:
        effective_jql = f"project = {project} ORDER BY issuetype DESC, key ASC"

    raw_issues = client.search_jql_all(
        jql=effective_jql,
        fields=PULL_FIELDS,
        max_results=max_results,
    )

    base = project_dir(project)
    written: list[str] = []

    if dry_run:
        for issue in raw_issues:
            yaml_dict = issue_to_yaml_dict(issue)
            dir_name = type_dir(yaml_dict["type"])
            filepath = base / dir_name / f"{yaml_dict['key']}.yaml"
            written.append(str(filepath))
        return {
            "action": "would_pull",
            "issues": len(raw_issues),
            "files": written,
            "jql": effective_jql,
        }

    # Ensure directories exist
    for dir_name in set(TYPE_DIR_MAP.values()):
        (base / dir_name).mkdir(parents=True, exist_ok=True)

    for issue in raw_issues:
        yaml_dict = issue_to_yaml_dict(issue)
        dir_name = type_dir(yaml_dict["type"])
        filepath = base / dir_name / f"{yaml_dict['key']}.yaml"
        # Preserve local-only fields (e.g. summary_ai) from any existing file.
        if filepath.exists():
            try:
                existing = yaml.safe_load(filepath.read_text()) or {}
                if isinstance(existing, dict) and "summary_ai" in existing:
                    yaml_dict["summary_ai"] = existing["summary_ai"]
            except yaml.YAMLError:
                pass
        filepath.write_text(_dump_yaml(yaml_dict))
        written.append(str(filepath))

    # Write metadata
    metadata = {
        "last_pull": datetime.now(timezone.utc).isoformat(),
        "jql": effective_jql,
        "project": project,
        "issue_count": len(raw_issues),
    }
    (base / METADATA_FILE).write_text(json.dumps(metadata, indent=2))

    return {
        "action": "pulled",
        "issues": len(raw_issues),
        "files": written,
        "jql": effective_jql,
        "metadata_file": str(base / METADATA_FILE),
    }


# -- Diff (local vs remote) --

def diff_issues(
    client: JiraClient,
    project: str,
    jql: str | None = None,
    max_results: int = 500,
) -> dict:
    """Compare local YAML files against live Jira state.

    Returns a dict with changes categorized as:
    - modified: fields differ between local YAML and Jira
    - local_only: files exist locally but issue not found in Jira
    - remote_only: issues in Jira but no local YAML file
    """
    base = project_dir(project)
    local_issues = _load_all_local(base)

    effective_jql = jql or f"project = {project} ORDER BY key ASC"
    raw_issues = client.search_jql_all(
        jql=effective_jql,
        fields=PULL_FIELDS,
        max_results=max_results,
    )

    remote_map: dict[str, dict] = {}
    for issue in raw_issues:
        yaml_dict = issue_to_yaml_dict(issue)
        remote_map[yaml_dict["key"]] = yaml_dict

    local_keys = set(local_issues.keys())
    remote_keys = set(remote_map.keys())

    changes: list[dict] = []

    for key in sorted(local_keys & remote_keys):
        field_diffs = _diff_fields(local_issues[key], remote_map[key])
        if field_diffs:
            changes.append({
                "key": key,
                "action": "modified",
                "fields": field_diffs,
            })

    for key in sorted(local_keys - remote_keys):
        changes.append({
            "key": key,
            "action": "local_only",
            "summary": local_issues[key].get("summary", ""),
        })

    for key in sorted(remote_keys - local_keys):
        changes.append({
            "key": key,
            "action": "remote_only",
            "summary": remote_map[key].get("summary", ""),
        })

    return {"changes": changes, "total": len(changes)}


def _diff_fields(local: dict, remote: dict) -> list[dict]:
    """Compare two issue dicts and return list of field differences."""
    diffs = []
    for field in DIFFABLE_FIELDS:
        local_val = local.get(field, "")
        remote_val = remote.get(field, "")
        if _normalize_value(local_val) != _normalize_value(remote_val):
            diffs.append({
                "field": field,
                "local": local_val,
                "remote": remote_val,
            })
    return diffs


def _normalize_value(val: Any) -> Any:
    """Normalize a value for comparison."""
    if val is None:
        return ""
    if isinstance(val, list) and not val:
        return ""
    if isinstance(val, list):
        return sorted(str(v) for v in val)
    return str(val).strip()


def _load_all_local(base: Path, skip_snapshots: bool = True) -> dict[str, dict]:
    """Load all YAML files from the sync directory into a key->dict map."""
    issues: dict[str, dict] = {}
    if not base.exists():
        return issues
    snapshots_dir = base / "snapshots"
    for yaml_file in base.rglob("*.yaml"):
        if skip_snapshots and yaml_file.is_relative_to(snapshots_dir):
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if isinstance(data, dict) and "key" in data:
                issues[data["key"]] = data
        except Exception:
            pass
    return issues


# -- Push --

def push_issues(
    client: JiraClient,
    project: str,
    keys: list[str] | None = None,
    dry_run: bool = False,
    max_results: int = 500,
) -> dict:
    """Push local changes to Jira, sending only changed fields.

    1. Load local YAML files
    2. Fetch current Jira state for those issues
    3. Diff each issue
    4. Build minimal update payload per issue
    5. PUT to Jira (unless dry_run)
    """
    base = project_dir(project)
    local_issues = _load_all_local(base)

    if keys:
        local_issues = {k: v for k, v in local_issues.items() if k in keys}

    if not local_issues:
        return {"action": "pushed", "results": [], "total": 0, "message": "No local issues found"}

    # Fetch live state for comparison
    issue_keys = list(local_issues.keys())
    keys_jql = f"key in ({','.join(issue_keys)})"
    raw_issues = client.search_jql_all(
        jql=keys_jql,
        fields=PULL_FIELDS,
        max_results=max_results,
    )

    remote_map: dict[str, dict] = {}
    for issue in raw_issues:
        yaml_dict = issue_to_yaml_dict(issue)
        remote_map[yaml_dict["key"]] = yaml_dict

    results: list[dict] = []

    for key, local in sorted(local_issues.items()):
        remote = remote_map.get(key)
        if not remote:
            results.append({"key": key, "action": "skipped", "reason": "not found in Jira"})
            continue

        field_diffs = _diff_fields(local, remote)
        if not field_diffs:
            continue

        update_payload = _build_update_payload(field_diffs)

        if dry_run:
            results.append({
                "key": key,
                "action": "would_update",
                "fields": [d["field"] for d in field_diffs],
            })
            continue

        # Separate transition from field updates
        needs_transition = any(d["field"] == "status" for d in field_diffs)
        target_status = local.get("status", "")

        # Remove transition marker from field payload
        field_payload = {k: v for k, v in update_payload.items() if k != "_transition"}

        if field_payload:
            client.put(client.platform(f"/issue/{key}"), json={"fields": field_payload})

        if needs_transition and target_status:
            _transition_issue(client, key, target_status)

        results.append({
            "key": key,
            "action": "updated",
            "fields": [d["field"] for d in field_diffs],
        })

    return {"action": "pushed", "results": results, "total": len(results)}


def _build_update_payload(diffs: list[dict]) -> dict:
    """Build a minimal Jira update payload from field diffs."""
    payload: dict = {}

    for diff in diffs:
        field = diff["field"]
        local_val = diff["local"]

        if field == "summary":
            payload["summary"] = local_val
        elif field == "type":
            payload["issuetype"] = {"name": local_val}
        elif field == "priority":
            payload["priority"] = {"name": local_val}
        elif field == "assignee":
            # Jira requires accountId, not displayName.
            # Skip for now -- future enhancement: user lookup cache.
            pass
        elif field == "components":
            if isinstance(local_val, list):
                payload["components"] = [{"name": c} for c in local_val]
            elif isinstance(local_val, str) and local_val:
                payload["components"] = [{"name": c.strip()} for c in local_val.split(",")]
        elif field == "labels":
            if isinstance(local_val, list):
                payload["labels"] = local_val
            elif isinstance(local_val, str):
                payload["labels"] = [label.strip() for label in local_val.split(",") if label.strip()]
        elif field == "parent":
            if local_val:
                payload["parent"] = {"key": local_val}
        elif field == "description":
            if local_val:
                from ebjira.commands.issue import _markdown_to_adf
                payload["description"] = _markdown_to_adf(local_val)
        elif field == "status":
            payload["_transition"] = True

    return payload


def _transition_issue(client: JiraClient, key: str, target_status: str) -> None:
    """Transition an issue to a target status by name."""
    try:
        data = client.get(client.platform(f"/issue/{key}/transitions"))
        transitions = data.get("transitions", [])

        for t in transitions:
            to_status = (t.get("to") or {}).get("name", "")
            if to_status.lower() == target_status.lower():
                client.post(client.platform(f"/issue/{key}/transitions"), json={
                    "transition": {"id": t["id"]}
                })
                return

        for t in transitions:
            if t.get("name", "").lower() == target_status.lower():
                client.post(client.platform(f"/issue/{key}/transitions"), json={
                    "transition": {"id": t["id"]}
                })
                return
    except Exception:
        pass


# -- Snapshots --

def create_snapshot(project: str) -> dict:
    """Copy current sync state to a timestamped snapshot directory."""
    base = project_dir(project)
    if not base.exists():
        return {"error": f"No sync directory found for project {project}"}

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    snapshot_dir = base / "snapshots" / timestamp

    for child in base.iterdir():
        if child.is_dir() and child.name != "snapshots":
            shutil.copytree(child, snapshot_dir / child.name)

    meta_file = base / METADATA_FILE
    if meta_file.exists():
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(meta_file, snapshot_dir / METADATA_FILE)

    file_count = sum(1 for _ in snapshot_dir.rglob("*.yaml"))

    return {
        "action": "snapshot_created",
        "path": str(snapshot_dir),
        "timestamp": timestamp,
        "files": file_count,
    }


def list_snapshots(project: str) -> list[dict]:
    """List all snapshots for a project."""
    base = project_dir(project)
    snapshots_dir = base / "snapshots"
    if not snapshots_dir.exists():
        return []

    results = []
    for snap in sorted(snapshots_dir.iterdir()):
        if snap.is_dir():
            file_count = sum(1 for _ in snap.rglob("*.yaml"))
            results.append({
                "timestamp": snap.name,
                "path": str(snap),
                "files": file_count,
            })
    return results


def diff_snapshots(project: str, snapshot_a: str, snapshot_b: str) -> dict:
    """Diff two snapshots (or 'current' for the live sync dir)."""
    base = project_dir(project)

    dir_a = base if snapshot_a == "current" else base / "snapshots" / snapshot_a
    dir_b = base if snapshot_b == "current" else base / "snapshots" / snapshot_b

    issues_a = _load_all_local(dir_a, skip_snapshots=(snapshot_a == "current"))
    issues_b = _load_all_local(dir_b, skip_snapshots=(snapshot_b == "current"))

    keys_a = set(issues_a.keys())
    keys_b = set(issues_b.keys())

    changes: list[dict] = []

    for key in sorted(keys_b - keys_a):
        changes.append({"key": key, "action": "added", "summary": issues_b[key].get("summary", "")})

    for key in sorted(keys_a - keys_b):
        changes.append({"key": key, "action": "removed", "summary": issues_a[key].get("summary", "")})

    for key in sorted(keys_a & keys_b):
        field_diffs = _diff_fields(issues_a[key], issues_b[key])
        if field_diffs:
            changes.append({"key": key, "action": "modified", "fields": field_diffs})

    return {
        "snapshot_a": snapshot_a,
        "snapshot_b": snapshot_b,
        "changes": changes,
        "total": len(changes),
    }

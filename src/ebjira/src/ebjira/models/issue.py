"""Pydantic models for Jira issues."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserRef(BaseModel):
    """Lightweight user reference (appears in assignee, reporter, etc.)."""

    account_id: str = Field(alias="accountId", default="")
    display_name: str = Field(alias="displayName", default="")
    email_address: str = Field(alias="emailAddress", default="")

    model_config = {"populate_by_name": True}


class StatusRef(BaseModel):
    """Status reference."""

    name: str = ""
    id: str = ""
    status_category: dict[str, Any] = Field(alias="statusCategory", default_factory=dict)

    model_config = {"populate_by_name": True}


class IssueTypeRef(BaseModel):
    """Issue type reference."""

    id: str = ""
    name: str = ""
    subtask: bool = False

    model_config = {"populate_by_name": True}


class PriorityRef(BaseModel):
    """Priority reference."""

    id: str = ""
    name: str = ""

    model_config = {"populate_by_name": True}


class ProjectRef(BaseModel):
    """Project reference."""

    id: str = ""
    key: str = ""
    name: str = ""

    model_config = {"populate_by_name": True}


class Comment(BaseModel):
    """Issue comment."""

    id: str = ""
    author: UserRef | None = None
    body: Any = None  # ADF or string
    created: str = ""
    updated: str = ""

    model_config = {"populate_by_name": True}

    def body_text(self) -> str:
        """Extract plain text from ADF body or return string body."""
        if isinstance(self.body, str):
            return self.body
        if isinstance(self.body, dict):
            return _extract_adf_text(self.body)
        return str(self.body) if self.body else ""


class Transition(BaseModel):
    """Issue transition."""

    id: str = ""
    name: str = ""
    to: StatusRef | None = None

    model_config = {"populate_by_name": True}


class IssueSummary(BaseModel):
    """Compact issue representation for list views."""

    key: str = ""
    summary: str = ""
    status: str = ""
    assignee: str = ""
    issue_type: str = Field(default="", alias="issuetype")
    priority: str = ""
    labels: list[str] = Field(default_factory=list)
    created: str = ""
    updated: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> IssueSummary:
        """Parse from raw Jira API response."""
        fields = data.get("fields", {})
        return cls(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            status=_nested_name(fields, "status"),
            assignee=_nested_name(fields, "assignee", key="displayName"),
            issuetype=_nested_name(fields, "issuetype"),
            priority=_nested_name(fields, "priority"),
            labels=fields.get("labels", []),
            created=fields.get("created", ""),
            updated=fields.get("updated", ""),
        )


class IssueDetail(BaseModel):
    """Full issue representation for view."""

    key: str = ""
    summary: str = ""
    status: str = ""
    assignee: str = ""
    reporter: str = ""
    issue_type: str = ""
    priority: str = ""
    project: str = ""
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)
    description: str = ""
    created: str = ""
    updated: str = ""
    resolution: str = ""
    epic_key: str = ""
    sprint: str = ""
    comments: list[dict] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> IssueDetail:
        """Parse from raw Jira API response."""
        fields = data.get("fields", {})
        comments_data = fields.get("comment", {})
        comments = []
        for c in comments_data.get("comments", []):
            comment = Comment.model_validate(c)
            comments.append({
                "id": comment.id,
                "author": comment.author.display_name if comment.author else "",
                "body": comment.body_text(),
                "created": comment.created,
            })

        # Sprint can be in customfield or direct
        sprint_name = ""
        sprint_field = fields.get("sprint")
        if isinstance(sprint_field, dict):
            sprint_name = sprint_field.get("name", "")

        return cls(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            status=_nested_name(fields, "status"),
            assignee=_nested_name(fields, "assignee", key="displayName"),
            reporter=_nested_name(fields, "reporter", key="displayName"),
            issue_type=_nested_name(fields, "issuetype"),
            priority=_nested_name(fields, "priority"),
            project=_nested_name(fields, "project", key="key"),
            labels=fields.get("labels", []),
            components=[c.get("name", "") for c in fields.get("components", [])],
            fix_versions=[v.get("name", "") for v in fields.get("fixVersions", [])],
            description=_extract_description(fields.get("description")),
            created=fields.get("created", ""),
            updated=fields.get("updated", ""),
            resolution=_nested_name(fields, "resolution"),
            epic_key=fields.get("parent", {}).get("key", "") if fields.get("parent") else "",
            sprint=sprint_name,
            comments=comments,
        )


# ── Helpers ──


def _nested_name(fields: dict, field_name: str, key: str = "name") -> str:
    """Extract a name from a nested Jira field like {name: X}."""
    field = fields.get(field_name)
    if isinstance(field, dict):
        return field.get(key, "")
    return ""


def _extract_adf_text(adf: dict, list_depth: int = 0) -> str:
    """Recursively extract markdown-formatted text from Atlassian Document Format.

    Round-trips with _markdown_to_adf in commands/issue.py:
    - heading nodes → '## Text' (level controls hash count)
    - bulletList/listItem nodes → '- Text' (one per item)
    - text nodes with marks → **bold** / *italic*
    - paragraphs → trailing newline
    """
    node_type = adf.get("type", "")

    if node_type == "text":
        text = adf.get("text", "")
        marks = adf.get("marks", [])
        for mark in marks:
            mark_type = mark.get("type", "")
            if mark_type == "strong":
                text = f"**{text}**"
            elif mark_type == "em":
                text = f"*{text}*"
            elif mark_type == "code":
                text = f"`{text}`"
        return text

    if node_type == "heading":
        level = adf.get("attrs", {}).get("level", 1)
        prefix = "#" * level
        inner = "".join(_extract_adf_text(c, list_depth) for c in adf.get("content", []))
        return f"{prefix} {inner}\n\n"

    if node_type == "paragraph":
        inner = "".join(_extract_adf_text(c, list_depth) for c in adf.get("content", []))
        # In a list item, paragraphs don't add their own newlines (the listItem handles it)
        if list_depth > 0:
            return inner
        return inner + "\n\n"

    if node_type == "bulletList":
        items = [_extract_adf_text(c, list_depth + 1) for c in adf.get("content", [])]
        return "".join(items) + "\n"

    if node_type == "orderedList":
        items = []
        for i, c in enumerate(adf.get("content", []), start=1):
            inner = _extract_adf_text(c, list_depth + 1).rstrip()
            # Strip the leading "- " that listItem would add and replace with "N. "
            if inner.startswith("- "):
                inner = inner[2:]
            items.append(f"{i}. {inner}\n")
        return "".join(items) + "\n"

    if node_type == "listItem":
        inner = "".join(_extract_adf_text(c, list_depth) for c in adf.get("content", []))
        return f"- {inner.rstrip()}\n"

    if node_type == "codeBlock":
        lang = adf.get("attrs", {}).get("language", "")
        inner = "".join(_extract_adf_text(c, list_depth) for c in adf.get("content", []))
        return f"```{lang}\n{inner}\n```\n\n"

    # Unknown / container nodes — recurse without adding markup
    content = adf.get("content", [])
    return "".join(_extract_adf_text(c, list_depth) for c in content)


def _extract_description(desc: Any) -> str:
    """Extract description as plain text from ADF or string."""
    if desc is None:
        return ""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return _extract_adf_text(desc).strip()
    return str(desc)

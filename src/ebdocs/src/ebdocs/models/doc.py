"""Pydantic models for Google Docs resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocSummary(BaseModel):
    """Summary of a Google Doc (from Drive file listing)."""

    id: str = Field(description="Document/file ID")
    title: str = Field(description="Document title")
    created_time: datetime | None = Field(None, description="Creation timestamp")
    modified_time: datetime | None = Field(None, description="Last modified timestamp")
    url: str = Field(default="", description="Web view URL")

    @classmethod
    def from_drive_file(cls, file: dict) -> DocSummary:
        """Create from a Drive files().list() response item."""
        return cls(
            id=file.get("id", ""),
            title=file.get("name", ""),
            created_time=file.get("createdTime"),
            modified_time=file.get("modifiedTime"),
            url=file.get("webViewLink", ""),
        )


class DocDetail(DocSummary):
    """Full document detail including content."""

    content_text: str = Field(default="", description="Plain text content of the document")
    word_count: int = Field(default=0, description="Approximate word count")

    @classmethod
    def from_doc_resource(cls, doc: dict, text: str = "") -> DocDetail:
        """Create from a Docs documents().get() response.

        Args:
            doc: The full document resource.
            text: Optional pre-extracted plain text content.
        """
        title = doc.get("title", "")
        doc_id = doc.get("documentId", "")

        # Extract text from body if not provided
        if not text:
            text = _extract_text(doc)

        word_count = len(text.split()) if text.strip() else 0

        return cls(
            id=doc_id,
            title=title,
            url=f"https://docs.google.com/document/d/{doc_id}/edit",
            content_text=text,
            word_count=word_count,
        )


def _extract_text(doc: dict) -> str:
    """Extract plain text from a Google Docs document resource."""
    body = doc.get("body", {})
    content = body.get("content", [])
    parts: list[str] = []

    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))

    return "".join(parts)


class Permission(BaseModel):
    """A permission on a Google Drive file."""

    id: str = Field(description="Permission ID")
    email: str = Field(default="", description="Email address of the grantee")
    role: str = Field(description="Permission role (reader, commenter, writer, owner)")
    type: str = Field(description="Permission type (user, group, domain, anyone)")

    @classmethod
    def from_api(cls, perm: dict) -> Permission:
        """Create from a Drive permissions response item."""
        return cls(
            id=perm.get("id", ""),
            email=perm.get("emailAddress", ""),
            role=perm.get("role", ""),
            type=perm.get("type", ""),
        )


class Comment(BaseModel):
    """A comment on a Google Drive file."""

    id: str = Field(description="Comment ID")
    content: str = Field(default="", description="Comment text")
    author: str = Field(default="", description="Author display name")
    created_time: datetime | None = Field(None, description="Creation timestamp")
    resolved: bool = Field(default=False, description="Whether the comment is resolved")

    @classmethod
    def from_api(cls, comment: dict) -> Comment:
        """Create from a Drive comments response item."""
        author = comment.get("author", {})
        return cls(
            id=comment.get("id", ""),
            content=comment.get("content", ""),
            author=author.get("displayName", author.get("emailAddress", "")),
            created_time=comment.get("createdTime"),
            resolved=comment.get("resolved", False),
        )

"""Tolerant JSONL parsing of Claude Code session files.

Each line is one JSON object. We care about type == user|assistant lines and their
message.content blocks (text, tool_use, tool_result). Unknown line types
(file-history-snapshot, mode, permission-mode, summary, ...) are skipped, not errors.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Line:
    """One parsed JSONL line, with the fields extraction cares about."""

    raw: dict[str, Any]
    type: str
    uuid: str | None = None
    parent_uuid: str | None = None
    timestamp: str | None = None
    is_sidechain: bool = False
    is_meta: bool = False
    cwd: str | None = None
    git_branch: str | None = None
    version: str | None = None
    session_id: str | None = None
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    content: list[dict[str, Any]] = field(default_factory=list)
    # For user lines that carry a slash-command tag.
    command_name: str | None = None


def _extract_content(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


_CMD_TAG = "<command-name>"


def _command_name(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    text = content if isinstance(content, str) else ""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
    if _CMD_TAG in text:
        start = text.index(_CMD_TAG) + len(_CMD_TAG)
        end = text.find("</command-name>", start)
        if end != -1:
            return text[start:end].strip()
    return None


def parse_lines(text: str) -> Iterator[Line]:
    """Yield a Line for each user/assistant JSONL record; skip everything else."""
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        line_type = obj.get("type", "")
        if line_type not in ("user", "assistant"):
            continue

        message = obj.get("message", {}) or {}
        usage = message.get("usage", {}) or {}
        yield Line(
            raw=obj,
            type=line_type,
            uuid=obj.get("uuid"),
            parent_uuid=obj.get("parentUuid"),
            timestamp=obj.get("timestamp"),
            is_sidechain=bool(obj.get("isSidechain", False)),
            is_meta=bool(obj.get("isMeta", False)),
            cwd=obj.get("cwd"),
            git_branch=obj.get("gitBranch"),
            version=obj.get("version"),
            session_id=obj.get("sessionId"),
            model=message.get("model"),
            usage=usage if isinstance(usage, dict) else {},
            content=_extract_content(message),
            command_name=_command_name(message) if line_type == "user" else None,
        )

"""Pydantic models for the declarative Jira project manifest.

Validates manifest.yaml and provides typed access to all project configuration.
The manifest is the single source of truth for statuses, issue types, components,
workflows, labels, board config, and agent operating model.

See docs/design-jira-manifest.md for the full design.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ProjectConfig(BaseModel):
    """Top-level project identity."""

    key: str
    name: str
    type: str = "company-managed"
    site: str = ""


class IssueTypeConfig(BaseModel):
    """An issue type definition."""

    name: str
    hierarchy: int = 0
    description: str = ""


class StatusConfig(BaseModel):
    """A workflow status with its category."""

    name: str
    category: str  # TODO, IN_PROGRESS, DONE


class TransitionConfig(BaseModel):
    """A workflow transition between two statuses."""

    model_config = ConfigDict(populate_by_name=True)

    from_status: str = Field(alias="from")
    to_status: str = Field(alias="to")


class WorkflowConfig(BaseModel):
    """A workflow definition with its transitions."""

    name: str
    description: str = ""
    statuses: list[str] = []
    transitions: list[TransitionConfig] = []


class WorkflowSchemeConfig(BaseModel):
    """A workflow scheme that maps workflows to issue types."""

    name: str
    description: str = ""
    default_workflow: str = ""


class ComponentConfig(BaseModel):
    """A project component (application context)."""

    name: str
    description: str = ""


class BoardColumnConfig(BaseModel):
    """A board column mapping statuses to visual columns."""

    name: str
    statuses: list[str] = []


class QuickFilterConfig(BaseModel):
    """A board quick filter with a JQL expression."""

    name: str
    jql: str


class BoardConfig(BaseModel):
    """Board configuration including columns and quick filters."""

    name: str = ""
    columns: list[BoardColumnConfig] = []
    quick_filters: list[QuickFilterConfig] = []


class AgentTransitionConfig(BaseModel):
    """An allowed agent transition between statuses."""

    model_config = ConfigDict(populate_by_name=True)

    from_status: str = Field(alias="from")
    to_status: str = Field(alias="to")


class AgentForbiddenConfig(BaseModel):
    """A forbidden agent transition (agent cannot move issues to this status)."""

    model_config = ConfigDict(populate_by_name=True)

    to_status: str = Field(alias="to")


class AgentConfig(BaseModel):
    """AI agent operating model configuration."""

    name: str = ""
    pick_up: dict[str, str] = {}
    rework: dict[str, str] = {}
    allowed_transitions: list[AgentTransitionConfig] = []
    forbidden_transitions: list[AgentForbiddenConfig] = []
    labels_agent_adds: list[str] = []
    labels_agent_never_touches: list[str] = []
    checkin_epic: str = ""
    branch_convention: str = ""


class EpicConfig(BaseModel):
    """A known epic with its key and summary."""

    key: str
    summary: str


class LabelsConfig(BaseModel):
    """Label taxonomy organized by purpose."""

    ai_workflow: list[str] = []
    deliverable_kinds: list[str] = []
    tool_overrides: list[str] = []
    audience: list[str] = []


class RetiredConfig(BaseModel):
    """Retired configuration items tracked for migration purposes."""

    statuses: list[str] = []


class Manifest(BaseModel):
    """The complete project manifest — single source of truth."""

    version: str = "1"
    project: ProjectConfig
    issue_types: list[IssueTypeConfig] = []
    statuses: list[StatusConfig] = []
    workflow: WorkflowConfig | None = None
    workflow_scheme: WorkflowSchemeConfig | None = None
    components: list[ComponentConfig] = []
    labels: LabelsConfig = LabelsConfig()
    board: BoardConfig = BoardConfig()
    agent: AgentConfig = AgentConfig()
    epics: list[EpicConfig] = []
    retired: RetiredConfig = RetiredConfig()


def _default_manifest_path() -> Path:
    """Return the default manifest.yaml path.

    Search order:
    1. JIRA_MANIFEST_FILE env var (set by Docker wrapper or consumer)
    2. /app/manifests/manifest.yaml (Docker container)
    3. manifests/jira/manifest.yaml (repo root cwd — canonical layout)
    4. error
    """
    import os

    env_path = os.environ.get("JIRA_MANIFEST_FILE")
    if env_path:
        return Path(env_path)

    candidates = [
        Path("/app/manifests/manifest.yaml"),
        Path("manifests/jira/manifest.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[1]  # fallback to manifests/jira/ for error message


def load_manifest(path: str | Path | None = None) -> Manifest:
    """Load and validate a manifest YAML file.

    Args:
        path: Path to the manifest file. If None, uses the default
              manifest.yaml in the jira-cli directory root.

    Returns:
        A validated Manifest object.

    Raises:
        FileNotFoundError: If the manifest file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
        pydantic.ValidationError: If the YAML doesn't match the schema.
    """
    if path is None:
        path = _default_manifest_path()
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    return Manifest.model_validate(raw)

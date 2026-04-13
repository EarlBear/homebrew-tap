"""Pydantic models for Jira projects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectSummary(BaseModel):
    """Compact project representation for list views."""

    id: str = ""
    key: str = ""
    name: str = ""
    project_type_key: str = Field(default="", alias="projectTypeKey")
    style: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> ProjectSummary:
        return cls(
            id=data.get("id", ""),
            key=data.get("key", ""),
            name=data.get("name", ""),
            projectTypeKey=data.get("projectTypeKey", ""),
            style=data.get("style", ""),
        )


class ProjectDetail(BaseModel):
    """Full project representation."""

    id: str = ""
    key: str = ""
    name: str = ""
    description: str = ""
    project_type_key: str = ""
    style: str = ""
    lead: str = ""
    url: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> ProjectDetail:
        lead = data.get("lead", {})
        return cls(
            id=data.get("id", ""),
            key=data.get("key", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            project_type_key=data.get("projectTypeKey", ""),
            style=data.get("style", ""),
            lead=lead.get("displayName", "") if isinstance(lead, dict) else "",
            url=data.get("url", ""),
        )


class Component(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    lead: str = ""
    assignee_type: str = Field(default="", alias="assigneeType")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> Component:
        lead = data.get("lead", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            lead=lead.get("displayName", "") if isinstance(lead, dict) else "",
            assigneeType=data.get("assigneeType", ""),
        )


class Version(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    released: bool = False
    archived: bool = False
    release_date: str = Field(default="", alias="releaseDate")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> Version:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            released=data.get("released", False),
            archived=data.get("archived", False),
            releaseDate=data.get("releaseDate", ""),
        )

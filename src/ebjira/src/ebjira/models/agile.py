"""Pydantic models for Jira Agile (boards, sprints, epics)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoardSummary(BaseModel):
    id: int = 0
    name: str = ""
    board_type: str = Field(default="", alias="type")
    project_key: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> BoardSummary:
        location = data.get("location", {})
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            type=data.get("type", ""),
            project_key=location.get("projectKey", ""),
        )


class SprintSummary(BaseModel):
    id: int = 0
    name: str = ""
    state: str = ""
    start_date: str = Field(default="", alias="startDate")
    end_date: str = Field(default="", alias="endDate")
    complete_date: str = Field(default="", alias="completeDate")
    board_id: int = Field(default=0, alias="originBoardId")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> SprintSummary:
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            state=data.get("state", ""),
            startDate=data.get("startDate", ""),
            endDate=data.get("endDate", ""),
            completeDate=data.get("completeDate", ""),
            originBoardId=data.get("originBoardId", 0),
        )


class BoardColumn(BaseModel):
    name: str = ""
    status_names: list[str] = []
    min_issues: int = 0
    max_issues: int = 0


class EpicSummary(BaseModel):
    id: int = 0
    key: str = ""
    name: str = ""
    summary: str = ""
    status: str = ""
    done: bool = False

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> EpicSummary:
        fields = data.get("fields", {})
        status = fields.get("status", {})
        return cls(
            id=data.get("id", 0),
            key=data.get("key", ""),
            name=fields.get("summary", data.get("name", "")),
            summary=fields.get("summary", ""),
            status=status.get("name", "") if isinstance(status, dict) else "",
            done=data.get("done", False),
        )

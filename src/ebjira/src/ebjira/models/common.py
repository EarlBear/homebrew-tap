"""Pydantic models for common Jira entities."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IssueType(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    subtask: bool = False
    hierarchy_level: int = Field(default=0, alias="hierarchyLevel")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> IssueType:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            subtask=data.get("subtask", False),
            hierarchyLevel=data.get("hierarchyLevel", 0),
        )


class Status(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""

    @classmethod
    def from_jira(cls, data: dict) -> Status:
        cat = data.get("statusCategory", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=cat.get("name", "") if isinstance(cat, dict) else "",
        )


class Priority(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""

    @classmethod
    def from_jira(cls, data: dict) -> Priority:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
        )


class Resolution(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""

    @classmethod
    def from_jira(cls, data: dict) -> Resolution:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
        )


class UserSummary(BaseModel):
    account_id: str = Field(default="", alias="accountId")
    display_name: str = Field(default="", alias="displayName")
    email_address: str = Field(default="", alias="emailAddress")
    active: bool = True

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> UserSummary:
        return cls(
            accountId=data.get("accountId", ""),
            displayName=data.get("displayName", ""),
            emailAddress=data.get("emailAddress", ""),
            active=data.get("active", True),
        )


class Attachment(BaseModel):
    id: str = ""
    filename: str = ""
    size: int = 0
    mime_type: str = Field(default="", alias="mimeType")
    author: str = ""
    created: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_jira(cls, data: dict) -> Attachment:
        author = data.get("author", {})
        return cls(
            id=data.get("id", ""),
            filename=data.get("filename", ""),
            size=data.get("size", 0),
            mimeType=data.get("mimeType", ""),
            author=author.get("displayName", "") if isinstance(author, dict) else "",
            created=data.get("created", ""),
        )


class Filter(BaseModel):
    id: str = ""
    name: str = ""
    jql: str = ""
    owner: str = ""
    favourite: bool = False

    @classmethod
    def from_jira(cls, data: dict) -> Filter:
        owner = data.get("owner", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            jql=data.get("jql", ""),
            owner=owner.get("displayName", "") if isinstance(owner, dict) else "",
            favourite=data.get("favourite", False),
        )


class Workflow(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    is_default: bool = False

    @classmethod
    def from_jira(cls, data: dict) -> Workflow:
        return cls(
            id=data.get("id", {}).get("entityId", "") if isinstance(data.get("id"), dict) else data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            is_default=data.get("isDefault", False),
        )


class WorkflowTransition(BaseModel):
    id: str = ""
    name: str = ""
    from_statuses: list[str] = []
    to_status: str = ""
    type: str = ""  # INITIAL, GLOBAL, DIRECTED

    @classmethod
    def from_jira(cls, data: dict) -> WorkflowTransition:
        from_refs = data.get("from", [])
        from_names: list[str] = []
        for ref in from_refs:
            if isinstance(ref, dict):
                from_names.append(ref.get("name", ref.get("id", "")))
            else:
                from_names.append(str(ref))
        to_ref = data.get("to", {})
        to_name = to_ref.get("name", to_ref.get("id", "")) if isinstance(to_ref, dict) else str(to_ref) if to_ref else ""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            from_statuses=from_names,
            to_status=to_name,
            type=data.get("type", ""),
        )


class WorkflowDetail(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    statuses: list[str] = []
    transitions: list[WorkflowTransition] = []

    @classmethod
    def from_jira(cls, data: dict) -> WorkflowDetail:
        raw_statuses = data.get("statuses", [])
        status_names: list[str] = []
        for s in raw_statuses:
            if isinstance(s, dict):
                status_names.append(s.get("name", s.get("id", "")))
            else:
                status_names.append(str(s))
        raw_transitions = data.get("transitions", [])
        transitions = [WorkflowTransition.from_jira(t) for t in raw_transitions]
        wf_id = data.get("id", {})
        entity_id = wf_id.get("entityId", "") if isinstance(wf_id, dict) else str(wf_id)
        return cls(
            id=entity_id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            statuses=status_names,
            transitions=transitions,
        )


class WorkflowScheme(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    default_workflow: str = ""

    @classmethod
    def from_jira(cls, data: dict) -> WorkflowScheme:
        dw = data.get("defaultWorkflow", {})
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            default_workflow=dw.get("name", "") if isinstance(dw, dict) else str(dw),
        )


class IssueTypeScheme(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    default_issue_type_id: str = ""
    issue_type_ids: list[str] = []

    @classmethod
    def from_jira(cls, data: dict) -> IssueTypeScheme:
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            default_issue_type_id=data.get("defaultIssueTypeId", ""),
            issue_type_ids=data.get("issueTypeIds", []),
        )


class Dashboard(BaseModel):
    id: str = ""
    name: str = ""
    owner: str = ""
    view: str = ""

    @classmethod
    def from_jira(cls, data: dict) -> Dashboard:
        owner = data.get("owner", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            owner=owner.get("displayName", "") if isinstance(owner, dict) else "",
            view=data.get("view", ""),
        )

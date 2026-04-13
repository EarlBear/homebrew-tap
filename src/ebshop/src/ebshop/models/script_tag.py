"""Script tag models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScriptTag(BaseModel):
    """A Shopify script tag injection."""

    id: str = ""
    src: str | None = ""
    display_scope: str | None = Field(default="", alias="displayScope")
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> ScriptTag:
        return cls.model_validate(node)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "src": self.src,
            "display_scope": self.display_scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

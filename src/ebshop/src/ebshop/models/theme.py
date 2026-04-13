"""Theme and theme asset models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThemeAsset(BaseModel):
    """A theme asset (template, snippet, stylesheet, etc.)."""

    key: str = ""
    content_type: str | None = Field(default="", alias="content_type")
    size: int | None = None
    created_at: str | None = Field(default="", alias="created_at")
    updated_at: str | None = Field(default="", alias="updated_at")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> ThemeAsset:
        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "key": self.key,
            "content_type": self.content_type,
            "size": self.size or 0,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Theme(BaseModel):
    """A Shopify theme."""

    id: int = 0
    name: str = ""
    role: str | None = ""
    created_at: str | None = Field(default="", alias="created_at")
    updated_at: str | None = Field(default="", alias="updated_at")
    previewable: bool = False
    processing: bool = False

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Theme:
        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "previewable": self.previewable,
            "processing": self.processing,
        }

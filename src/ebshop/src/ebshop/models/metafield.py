"""Metafield model for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Metafield(BaseModel):
    """A Shopify metafield."""

    id: str = ""
    namespace: str = ""
    key: str = ""
    value: str | None = ""
    type: str | None = ""
    owner_type: str | None = Field(default="", alias="ownerType")
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Metafield:
        return cls.model_validate(node)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "key": self.key,
            "value": self.value,
            "type": self.type,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["owner_type"] = self.owner_type
        result["created_at"] = self.created_at
        result["updated_at"] = self.updated_at
        return result

"""Webhook subscription models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Webhook(BaseModel):
    """A Shopify webhook subscription."""

    id: str = ""
    topic: str = ""
    callback_url: str | None = Field(default="", alias="callbackUrl")
    format: str | None = ""
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Webhook:
        return cls.model_validate(node)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "callback_url": self.callback_url,
            "format": self.format,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

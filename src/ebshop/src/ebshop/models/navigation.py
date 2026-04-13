"""Navigation menu models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Menu(BaseModel):
    """A Shopify online store navigation menu."""

    id: str = ""
    title: str | None = ""
    handle: str | None = ""
    items_count: int | None = Field(default=None, alias="itemsCount")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Menu:
        return cls.model_validate(node)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "items_count": self.items_count,
        }

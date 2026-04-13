"""Page model for Shopify Online Store pages (REST Admin API)."""

from __future__ import annotations

from pydantic import BaseModel


class Page(BaseModel):
    """A Shopify Online Store page."""

    id: int = 0
    title: str = ""
    body_html: str | None = ""
    handle: str | None = ""
    author: str | None = ""
    created_at: str | None = ""
    updated_at: str | None = ""
    published_at: str | None = None
    template_suffix: str | None = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Page:
        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "author": self.author,
            "published": self.published_at is not None,
            "updated_at": self.updated_at,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["body_html"] = self.body_html
        result["created_at"] = self.created_at
        result["published_at"] = self.published_at or ""
        result["template_suffix"] = self.template_suffix
        return result

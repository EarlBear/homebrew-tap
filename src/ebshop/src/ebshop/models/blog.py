"""Blog and article models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Blog(BaseModel):
    """A Shopify blog."""

    id: int = 0
    title: str = ""
    handle: str | None = ""
    commentable: str | None = ""
    tags: str | None = ""
    created_at: str | None = Field(default="", alias="created_at")
    updated_at: str | None = Field(default="", alias="updated_at")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Blog:
        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "commentable": self.commentable,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Article(BaseModel):
    """A Shopify blog article."""

    id: int = 0
    title: str = ""
    body_html: str | None = Field(default="", alias="body_html")
    author: str | None = ""
    handle: str | None = ""
    tags: str | None = ""
    created_at: str | None = Field(default="", alias="created_at")
    updated_at: str | None = Field(default="", alias="updated_at")
    published_at: str | None = Field(default=None, alias="published_at")
    summary_html: str | None = Field(default="", alias="summary_html")
    blog_id: int = Field(default=0, alias="blog_id")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Article:
        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "handle": self.handle,
            "tags": self.tags,
            "blog_id": self.blog_id,
            "published_at": self.published_at or "",
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["body_html"] = self.body_html
        result["summary_html"] = self.summary_html
        return result

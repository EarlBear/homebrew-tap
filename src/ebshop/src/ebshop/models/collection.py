"""Collection models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebshop.models.common import Image


class Collection(BaseModel):
    """A Shopify collection (manual or smart)."""

    id: str = ""
    title: str = ""
    handle: str = ""
    description_html: str | None = Field(default="", alias="descriptionHtml")
    sort_order: str | None = Field(default="", alias="sortOrder")
    products_count: int = Field(default=0, alias="productsCount")
    updated_at: str = Field(default="", alias="updatedAt")
    image: Image | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Collection:
        """Parse a collection node from GraphQL response.

        Handles nested productsCount (count field) and image.
        """
        data = dict(node)

        # Flatten productsCount from {count: N} to int
        pc = data.get("productsCount")
        if isinstance(pc, dict):
            data["productsCount"] = pc.get("count", 0)

        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "sort_order": self.sort_order,
            "products_count": self.products_count,
            "updated_at": self.updated_at,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["description_html"] = self.description_html
        result["image"] = self.image.url if self.image else ""
        return result

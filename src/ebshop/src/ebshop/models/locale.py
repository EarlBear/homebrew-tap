"""Locale models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel


class ShopLocale(BaseModel):
    """A Shopify shop locale."""

    locale: str | None = ""
    name: str | None = ""
    primary: bool = False
    published: bool = False

    @classmethod
    def from_shopify(cls, node: dict) -> ShopLocale:
        """Parse a shop locale from GraphQL response."""
        return cls.model_validate({
            "locale": node.get("locale", ""),
            "name": node.get("name", ""),
            "primary": node.get("primary", False),
            "published": node.get("published", False),
        })

    def summary(self) -> dict:
        return {
            "locale": self.locale,
            "name": self.name,
            "primary": self.primary,
            "published": self.published,
        }

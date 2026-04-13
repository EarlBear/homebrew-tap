"""Translation models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel


class Translation(BaseModel):
    """A Shopify resource translation."""

    key: str | None = ""
    value: str | None = ""
    locale: str | None = ""
    outdated: bool = False

    @classmethod
    def from_shopify(cls, node: dict) -> Translation:
        """Parse a translation from GraphQL response."""
        return cls.model_validate({
            "key": node.get("key", ""),
            "value": node.get("value", ""),
            "locale": node.get("locale", ""),
            "outdated": node.get("outdated", False),
        })

    def summary(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "locale": self.locale,
            "outdated": self.outdated,
        }

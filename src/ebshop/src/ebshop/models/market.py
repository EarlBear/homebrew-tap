"""Market models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarketRegion(BaseModel):
    """A region within a market."""

    country_code: str | None = ""
    name: str | None = ""


class Market(BaseModel):
    """A Shopify market for international selling."""

    id: str = ""
    name: str | None = ""
    enabled: bool = False
    primary: bool = False
    currency_code: str | None = ""
    regions: list[dict] = Field(default_factory=list)

    @classmethod
    def from_shopify(cls, node: dict) -> Market:
        """Parse a market node from GraphQL response."""
        data: dict = {}
        data["id"] = node.get("id", "")
        data["name"] = node.get("name", "")
        data["enabled"] = node.get("enabled", False)
        data["primary"] = node.get("primary", False)

        # Currency settings
        currency = node.get("currencySettings", {})
        data["currency_code"] = currency.get("baseCurrency", {}).get("currencyCode", "") if currency else ""

        # Regions
        regions_conn = node.get("regions", {})
        edges = regions_conn.get("edges", []) if isinstance(regions_conn, dict) else []
        data["regions"] = []
        for edge in edges:
            region = edge.get("node", {})
            data["regions"].append({
                "country_code": region.get("country", {}).get("code", "")
                if "country" in region else region.get("code", ""),
                "name": region.get("name", ""),
            })

        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "primary": self.primary,
            "region_count": len(self.regions),
        }

    def detail(self) -> dict:
        result = self.summary()
        result["currency_code"] = self.currency_code
        result["regions"] = self.regions
        return result

"""Inventory models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InventoryLevel(BaseModel):
    """Inventory level at a specific location."""

    location_id: str = ""
    location_name: str = ""
    available: int = 0
    on_hand: int = 0

    @classmethod
    def from_shopify(cls, node: dict) -> InventoryLevel:
        """Parse an inventoryLevel node from GraphQL response."""
        location = node.get("location", {})
        quantities = node.get("quantities", [])
        available = 0
        on_hand = 0
        for q in quantities:
            if q.get("name") == "available":
                available = q.get("quantity", 0)
            elif q.get("name") == "on_hand":
                on_hand = q.get("quantity", 0)
        return cls(
            location_id=location.get("id", ""),
            location_name=location.get("name", ""),
            available=available,
            on_hand=on_hand,
        )

    def summary(self) -> dict:
        return {
            "location_id": self.location_id,
            "location_name": self.location_name,
            "available": self.available,
            "on_hand": self.on_hand,
        }


class Location(BaseModel):
    """A Shopify location."""

    id: str = ""
    name: str = ""
    city: str | None = ""
    province: str | None = ""
    country: str | None = ""
    is_active: bool = Field(default=False, alias="isActive")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Location:
        """Parse a location node from GraphQL response."""
        address = node.get("address", {}) or {}
        return cls(
            id=node.get("id", ""),
            name=node.get("name", ""),
            city=address.get("city", ""),
            province=address.get("province", ""),
            country=address.get("country", ""),
            is_active=node.get("isActive", False),
        )

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "province": self.province,
            "country": self.country,
            "is_active": self.is_active,
        }

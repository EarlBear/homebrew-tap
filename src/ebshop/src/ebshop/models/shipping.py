"""Pydantic models for Shopify Shipping / Delivery Profile resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ShippingZone(BaseModel):
    """A shipping zone from a delivery profile."""

    id: str = ""
    profile_id: str | None = ""
    profile_name: str | None = ""
    zone_name: str | None = ""
    countries: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def summary(self) -> dict:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "zone_name": self.zone_name,
            "countries": self.countries,
        }


class ShippingRate(BaseModel):
    """A shipping rate within a zone."""

    id: str = ""
    name: str | None = ""
    price_amount: str | None = ""
    price_currency: str | None = ""

    model_config = {"populate_by_name": True}

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": f"{self.price_amount} {self.price_currency}" if self.price_amount else "",
        }

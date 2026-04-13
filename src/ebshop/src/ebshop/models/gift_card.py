"""Gift card models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GiftCard(BaseModel):
    """A Shopify gift card."""

    id: str = ""
    balance: str | None = ""
    currency: str | None = ""
    initial_value: str | None = ""
    last_characters: str | None = ""
    note: str | None = ""
    enabled: bool = True
    created_at: str | None = ""
    expires_on: str | None = ""
    customer_id: str | None = ""

    @classmethod
    def from_shopify(cls, node: dict) -> GiftCard:
        """Parse a gift card node from GraphQL response."""
        data: dict = {}
        data["id"] = node.get("id", "")

        balance = node.get("balance", {})
        data["balance"] = balance.get("amount", "") if isinstance(balance, dict) else ""
        data["currency"] = balance.get("currencyCode", "") if isinstance(balance, dict) else ""

        initial = node.get("initialValue", {})
        data["initial_value"] = initial.get("amount", "") if isinstance(initial, dict) else ""

        data["last_characters"] = node.get("lastCharacters", "")
        data["note"] = node.get("note", "") or ""
        data["enabled"] = node.get("enabled", True)
        data["created_at"] = node.get("createdAt", "")
        data["expires_on"] = node.get("expiresOn", "") or ""

        customer = node.get("customer", {})
        data["customer_id"] = customer.get("id", "") if customer else ""

        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "balance": self.balance,
            "currency": self.currency,
            "last_characters": self.last_characters,
            "enabled": self.enabled,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["initial_value"] = self.initial_value
        result["note"] = self.note
        result["created_at"] = self.created_at
        result["expires_on"] = self.expires_on
        result["customer_id"] = self.customer_id
        return result

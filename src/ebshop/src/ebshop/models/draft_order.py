"""Pydantic models for Shopify DraftOrder resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebshop.models.common import MoneyV2


class DraftOrder(BaseModel):
    """A Shopify draft order."""

    id: str = ""
    name: str | None = ""
    status: str | None = ""
    note: str | None = ""
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")
    completed_at: str | None = Field(default="", alias="completedAt")
    invoice_url: str | None = Field(default="", alias="invoiceUrl")
    total_price: str | None = ""
    currency_code: str | None = ""
    customer_name: str | None = ""
    line_items_count: int = 0

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> DraftOrder:
        total = node.get("totalPriceSet", {}).get("shopMoney", {})
        customer = node.get("customer", {})
        customer_name = ""
        if customer:
            first = customer.get("firstName", "") or ""
            last = customer.get("lastName", "") or ""
            customer_name = f"{first} {last}".strip()
        line_items = node.get("lineItems", {}).get("edges", [])
        return cls(
            id=node.get("id", ""),
            name=node.get("name", ""),
            status=node.get("status", ""),
            note=node.get("note", ""),
            created_at=node.get("createdAt", ""),
            updated_at=node.get("updatedAt", ""),
            completed_at=node.get("completedAt", ""),
            invoice_url=node.get("invoiceUrl", ""),
            total_price=total.get("amount", ""),
            currency_code=total.get("currencyCode", ""),
            customer_name=customer_name,
            line_items_count=len(line_items),
        )

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "customer": self.customer_name,
            "total": f"{self.total_price} {self.currency_code}" if self.total_price else "",
            "created_at": self.created_at,
        }

    def detail(self) -> dict:
        result = self.summary()
        result.update({
            "note": self.note,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "invoice_url": self.invoice_url,
            "line_items_count": self.line_items_count,
        })
        return result

"""Pydantic models for Shopify Return resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Return(BaseModel):
    """A Shopify return."""

    id: str = ""
    status: str | None = ""
    order_id: str | None = ""
    name: str | None = ""
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")
    decline_reason: str | None = Field(default="", alias="declineReason")
    total_quantity: int = 0

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Return:
        order = node.get("order", {})
        line_items = node.get("returnLineItems", {}).get("edges", [])
        total_qty = sum(
            e.get("node", {}).get("quantity", 0) for e in line_items
        )
        return cls(
            id=node.get("id", ""),
            status=node.get("status", ""),
            order_id=order.get("id", "") if order else "",
            name=node.get("name", ""),
            created_at=node.get("createdAt", ""),
            updated_at=node.get("updatedAt", ""),
            decline_reason=node.get("declineReason", ""),
            total_quantity=total_qty,
        )

    def summary(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "name": self.name,
            "order_id": self.order_id,
            "total_quantity": self.total_quantity,
            "created_at": self.created_at,
        }

    def detail(self) -> dict:
        result = self.summary()
        result.update({
            "updated_at": self.updated_at,
            "decline_reason": self.decline_reason,
        })
        return result

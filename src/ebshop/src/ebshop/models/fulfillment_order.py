"""Pydantic models for Shopify FulfillmentOrder resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FulfillmentOrder(BaseModel):
    """A Shopify fulfillment order."""

    id: str = ""
    status: str | None = ""
    request_status: str | None = Field(default="", alias="requestStatus")
    assigned_location_name: str | None = ""
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")
    order_id: str | None = ""
    line_items_count: int = 0

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> FulfillmentOrder:
        location = node.get("assignedLocation", {})
        line_items = node.get("lineItems", {}).get("edges", [])
        return cls(
            id=node.get("id", ""),
            status=node.get("status", ""),
            request_status=node.get("requestStatus", ""),
            assigned_location_name=location.get("name", "") if location else "",
            created_at=node.get("createdAt", ""),
            updated_at=node.get("updatedAt", ""),
            order_id=node.get("orderId", ""),
            line_items_count=len(line_items),
        )

    def summary(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "request_status": self.request_status,
            "assigned_location": self.assigned_location_name,
            "line_items_count": self.line_items_count,
            "created_at": self.created_at,
        }

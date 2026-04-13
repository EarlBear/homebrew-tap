"""Pydantic models for Shopify Order resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebshop.models.common import MoneyV2


class LineItem(BaseModel):
    """A single line item within an order."""

    id: str = ""
    title: str = ""
    quantity: int = 0
    variant_title: str | None = Field(default="", alias="variantTitle")
    sku: str | None = ""
    original_total_set: MoneyV2 | None = Field(default=None, alias="originalTotalSet")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> LineItem:
        """Parse a Shopify lineItem node into a LineItem model."""
        money = data.get("originalTotalSet", {}).get("shopMoney")
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            quantity=data.get("quantity", 0),
            variant_title=data.get("variantTitle", ""),
            sku=data.get("sku", ""),
            original_total_set=MoneyV2(**money) if money else None,
        )

    def to_dict(self) -> dict:
        result: dict = {
            "id": self.id,
            "title": self.title,
            "quantity": self.quantity,
            "variant_title": self.variant_title,
            "sku": self.sku,
        }
        if self.original_total_set:
            result["original_total"] = self.original_total_set.display()
        return result


class Order(BaseModel):
    """Shopify order summary."""

    id: str = ""
    name: str = ""
    email: str | None = ""
    phone: str | None = ""
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")
    cancelled_at: str | None = Field(default=None, alias="cancelledAt")
    closed_at: str | None = Field(default=None, alias="closedAt")
    display_financial_status: str | None = Field(default="", alias="displayFinancialStatus")
    display_fulfillment_status: str | None = Field(default="", alias="displayFulfillmentStatus")
    total_price_set: MoneyV2 | None = Field(default=None, alias="totalPriceSet")
    subtotal_price_set: MoneyV2 | None = Field(default=None, alias="subtotalPriceSet")
    total_tax_set: MoneyV2 | None = Field(default=None, alias="totalTaxSet")
    currency_code: str | None = Field(default="", alias="currencyCode")
    line_items: list[LineItem] = Field(default_factory=list, alias="lineItems")
    customer_name: str | None = ""
    shipping_address: dict | None = Field(default=None, alias="shippingAddress")
    note: str | None = ""
    tags: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Order:
        """Parse a Shopify order GraphQL response node."""
        # Extract MoneyV2 fields (shopMoney from MoneyBag)
        total = data.get("totalPriceSet", {}).get("shopMoney")
        subtotal = data.get("subtotalPriceSet", {}).get("shopMoney")
        tax = data.get("totalTaxSet", {}).get("shopMoney")

        # Extract line items from edges
        line_item_edges = data.get("lineItems", {}).get("edges", [])
        line_items = [LineItem.from_shopify(e["node"]) for e in line_item_edges]

        # Extract customer name
        customer = data.get("customer")
        customer_name = ""
        if customer:
            first = customer.get("firstName", "") or ""
            last = customer.get("lastName", "") or ""
            customer_name = f"{first} {last}".strip()

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", ""),
            cancelled_at=data.get("cancelledAt"),
            closed_at=data.get("closedAt"),
            display_financial_status=data.get("displayFinancialStatus", ""),
            display_fulfillment_status=data.get("displayFulfillmentStatus", ""),
            total_price_set=MoneyV2(**total) if total else None,
            subtotal_price_set=MoneyV2(**subtotal) if subtotal else None,
            total_tax_set=MoneyV2(**tax) if tax else None,
            currency_code=data.get("currencyCode", ""),
            line_items=line_items,
            customer_name=customer_name,
            shipping_address=data.get("shippingAddress"),
            note=data.get("note", ""),
            tags=data.get("tags", []),
        )

    def to_summary(self) -> dict:
        """Compact dict for list output."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "customer": self.customer_name,
            "financial_status": self.display_financial_status,
            "fulfillment_status": self.display_fulfillment_status,
            "total": self.total_price_set.display() if self.total_price_set else "",
            "created_at": self.created_at,
        }

    def to_detail(self) -> dict:
        """Full dict for view output."""
        result = self.to_summary()
        result.update({
            "phone": self.phone,
            "updated_at": self.updated_at,
            "cancelled_at": self.cancelled_at or "",
            "closed_at": self.closed_at or "",
            "subtotal": self.subtotal_price_set.display() if self.subtotal_price_set else "",
            "tax": self.total_tax_set.display() if self.total_tax_set else "",
            "currency": self.currency_code,
            "note": self.note,
            "tags": self.tags,
            "shipping_address": self.shipping_address or {},
            "line_items": [li.to_dict() for li in self.line_items],
        })
        return result

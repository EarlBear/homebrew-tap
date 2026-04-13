"""Discount models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Discount(BaseModel):
    """A Shopify discount (code-based or automatic)."""

    id: str = ""
    title: str = ""
    status: str = ""
    code: str | None = ""
    discount_type: str | None = ""
    value: str | None = ""
    starts_at: str | None = Field(default="", alias="startsAt")
    ends_at: str | None = Field(default="", alias="endsAt")
    usage_count: int = Field(default=0, alias="usageCount")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Discount:
        """Parse a discountNode from GraphQL response.

        Handles the polymorphic discount union type (DiscountCodeBasic,
        DiscountAutomaticBasic) nested inside the discountNode wrapper.
        """
        data: dict = {}
        data["id"] = node.get("id", "")

        # The discount field contains the actual discount data
        discount = node.get("discount", node)

        data["title"] = discount.get("title", "")
        data["status"] = discount.get("status", "")
        data["startsAt"] = discount.get("startsAt", "")
        data["endsAt"] = discount.get("endsAt", "") or ""
        data["usageCount"] = discount.get("usageCount", 0) or discount.get("asyncUsageCount", 0)

        # Extract code (only for code-based discounts)
        codes = discount.get("codes", {})
        if isinstance(codes, dict):
            edges = codes.get("edges", [])
            if edges:
                data["code"] = edges[0].get("node", {}).get("code", "")
            else:
                data["code"] = ""
        else:
            data["code"] = ""

        # Extract discount value from customerGets.value
        customer_gets = discount.get("customerGets", {})
        value_obj = customer_gets.get("value", {}) if customer_gets else {}
        if "percentage" in value_obj:
            pct = value_obj["percentage"]
            data["discount_type"] = "percentage"
            data["value"] = str(round(float(pct) * 100, 2))
        elif "amount" in value_obj:
            amount = value_obj["amount"]
            data["discount_type"] = "fixed_amount"
            data["value"] = str(amount.get("amount", "0")) if isinstance(amount, dict) else str(amount)
        else:
            data["discount_type"] = ""
            data["value"] = ""

        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "code": self.code,
            "discount_type": self.discount_type,
            "value": self.value,
            "usage_count": self.usage_count,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["starts_at"] = self.starts_at
        result["ends_at"] = self.ends_at
        return result

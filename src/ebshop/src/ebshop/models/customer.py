"""Pydantic models for Shopify Customer resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebshop.models.common import MoneyV2


class CustomerAddress(BaseModel):
    """A customer mailing address."""

    address1: str | None = ""
    address2: str | None = ""
    city: str | None = ""
    province: str | None = ""
    country: str | None = ""
    zip: str | None = ""
    phone: str | None = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict | None) -> CustomerAddress | None:
        if not data:
            return None
        return cls.model_validate(data)

    def to_dict(self) -> dict:
        return {
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "province": self.province,
            "country": self.country,
            "zip": self.zip,
            "phone": self.phone,
        }


class CustomerOrder(BaseModel):
    """Minimal order summary nested under a customer."""

    id: str = ""
    name: str = ""
    total_price: MoneyV2 | None = Field(default=None, alias="totalPrice")
    created_at: str = Field(default="", alias="createdAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> CustomerOrder:
        money = data.get("totalPriceSet", {}).get("shopMoney")
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            total_price=MoneyV2(**money) if money else None,
            created_at=data.get("createdAt", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "total": self.total_price.display() if self.total_price else "",
            "created_at": self.created_at,
        }


class Customer(BaseModel):
    """A Shopify customer."""

    id: str = ""
    first_name: str | None = Field(default="", alias="firstName")
    last_name: str | None = Field(default="", alias="lastName")
    email: str | None = ""
    phone: str | None = ""
    created_at: str = Field(default="", alias="createdAt")
    updated_at: str = Field(default="", alias="updatedAt")
    orders_count: str = Field(default="0", alias="numberOfOrders")
    total_spent: MoneyV2 | None = Field(default=None, alias="amountSpent")
    tags: list[str] = Field(default_factory=list)
    note: str | None = ""
    verified_email: bool = Field(default=False, alias="verifiedEmail")
    state: str | None = ""
    default_address: CustomerAddress | None = Field(default=None, alias="defaultAddress")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, data: dict) -> Customer:
        """Parse a Shopify customer GraphQL response node."""
        node = dict(data)

        # Handle numberOfOrders — may be a string or missing
        orders_count = node.get("numberOfOrders")
        if orders_count is None:
            node["numberOfOrders"] = "0"
        else:
            node["numberOfOrders"] = str(orders_count)

        # Handle amountSpent
        amount_spent = node.get("amountSpent")
        if isinstance(amount_spent, dict) and "amount" in amount_spent:
            node["amountSpent"] = amount_spent
        else:
            node["amountSpent"] = None

        # Handle defaultAddress
        addr = node.get("defaultAddress")
        if isinstance(addr, dict):
            node["defaultAddress"] = addr
        else:
            node["defaultAddress"] = None

        return cls.model_validate(node)

    def to_summary(self) -> dict:
        """Compact dict for list output."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "orders_count": self.orders_count,
            "total_spent": self.total_spent.display() if self.total_spent else "",
            "state": self.state,
            "tags": ", ".join(self.tags) if self.tags else "",
        }

    def to_detail(self) -> dict:
        """Full dict for view output."""
        result = self.to_summary()
        result.update({
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "note": self.note,
            "verified_email": self.verified_email,
            "default_address": self.default_address.to_dict() if self.default_address else {},
        })
        return result

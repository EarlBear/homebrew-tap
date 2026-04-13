"""Pydantic models for analytics computed from order data."""

from __future__ import annotations

from pydantic import BaseModel


class SalesSummary(BaseModel):
    """Aggregated sales summary over a time period."""

    period_days: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    currency: str = ""
    average_order_value: float = 0.0
    unique_customers: int = 0
    fulfillment_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "period_days": self.period_days,
            "total_orders": self.total_orders,
            "total_revenue": round(self.total_revenue, 2),
            "currency": self.currency,
            "average_order_value": round(self.average_order_value, 2),
            "unique_customers": self.unique_customers,
            "fulfillment_rate": round(self.fulfillment_rate, 2),
        }


class TopProduct(BaseModel):
    """A product ranked by units sold."""

    rank: int = 0
    title: str = ""
    units_sold: int = 0
    revenue: float = 0.0
    currency: str = ""

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "units_sold": self.units_sold,
            "revenue": round(self.revenue, 2),
            "currency": self.currency,
        }


class TopCustomer(BaseModel):
    """A customer ranked by total spend."""

    rank: int = 0
    name: str = ""
    email: str = ""
    orders_count: int = 0
    total_spent: float = 0.0
    currency: str = ""

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "name": self.name,
            "email": self.email,
            "orders_count": self.orders_count,
            "total_spent": round(self.total_spent, 2),
            "currency": self.currency,
        }

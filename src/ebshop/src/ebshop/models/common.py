"""Common Shopify models shared across command groups."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MoneyV2(BaseModel):
    """Shopify money value with currency."""

    amount: str = ""
    currency_code: str = Field(default="", alias="currencyCode")

    model_config = {"populate_by_name": True}

    def display(self) -> str:
        return f"{self.amount} {self.currency_code}" if self.amount else ""


class Image(BaseModel):
    """Shopify image reference."""

    url: str = ""
    alt_text: str | None = Field(default="", alias="altText")
    width: int | None = None
    height: int | None = None

    model_config = {"populate_by_name": True}


class PageInfo(BaseModel):
    """GraphQL cursor pagination info."""

    has_next_page: bool = Field(default=False, alias="hasNextPage")
    has_previous_page: bool = Field(default=False, alias="hasPreviousPage")
    end_cursor: str | None = Field(default=None, alias="endCursor")
    start_cursor: str | None = Field(default=None, alias="startCursor")

    model_config = {"populate_by_name": True}

"""Product and variant models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebshop.models.common import Image, MoneyV2


class ProductVariant(BaseModel):
    """A product variant (size, color, etc.)."""

    id: str = ""
    title: str = ""
    sku: str | None = ""
    price: MoneyV2 | None = None
    compare_at_price: MoneyV2 | None = Field(default=None, alias="compareAtPrice")
    inventory_quantity: int = Field(default=0, alias="inventoryQuantity")
    weight: float | None = None
    weight_unit: str | None = Field(default="", alias="weightUnit")
    barcode: str | None = ""
    position: int = 0
    available_for_sale: bool = Field(default=False, alias="availableForSale")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> ProductVariant:
        return cls.model_validate(node)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "sku": self.sku,
            "price": self.price.display() if self.price else "",
            "compare_at_price": self.compare_at_price.display() if self.compare_at_price else "",
            "inventory_quantity": self.inventory_quantity,
            "barcode": self.barcode,
            "position": self.position,
            "available_for_sale": self.available_for_sale,
        }


class Product(BaseModel):
    """A Shopify product."""

    id: str = ""
    title: str = ""
    handle: str = ""
    status: str = ""
    vendor: str | None = ""
    product_type: str | None = Field(default="", alias="productType")
    tags: list[str] = Field(default_factory=list)
    total_variants: int = Field(default=0, alias="totalVariants")
    total_inventory: int = Field(default=0, alias="totalInventory")
    description_html: str | None = Field(default="", alias="descriptionHtml")
    created_at: str | None = Field(default="", alias="createdAt")
    updated_at: str | None = Field(default="", alias="updatedAt")
    images: list[Image] = Field(default_factory=list)
    featured_image: Image | None = Field(default=None, alias="featuredImage")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> Product:
        """Parse a product node from GraphQL response.

        Handles nested connections (images.edges) and count fields.
        """
        data = dict(node)

        # Flatten images connection
        images_conn = data.get("images")
        if isinstance(images_conn, dict) and "edges" in images_conn:
            data["images"] = [e["node"] for e in images_conn["edges"]]

        # totalVariants is now a top-level field from the query

        return cls.model_validate(data)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "status": self.status,
            "vendor": self.vendor,
            "product_type": self.product_type,
            "tags": ", ".join(self.tags) if self.tags else "",
            "total_variants": self.total_variants,
            "total_inventory": self.total_inventory,
        }

    def detail(self) -> dict:
        result = self.summary()
        result["description_html"] = self.description_html
        result["created_at"] = self.created_at
        result["updated_at"] = self.updated_at
        result["featured_image"] = self.featured_image.url if self.featured_image else ""
        return result

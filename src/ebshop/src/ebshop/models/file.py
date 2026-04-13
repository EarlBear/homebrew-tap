"""File/asset models for Shopify Admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class File(BaseModel):
    """A Shopify file (GenericFile or MediaImage)."""

    id: str = ""
    alt: str | None = ""
    url: str | None = ""
    status: str | None = Field(default="", alias="fileStatus")
    mime_type: str | None = Field(default="", alias="mimeType")
    created_at: str | None = Field(default="", alias="createdAt")
    original_file_size: int | None = Field(default=None, alias="originalFileSize")
    image_url: str | None = ""
    image_width: int | None = None
    image_height: int | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def from_shopify(cls, node: dict) -> File:
        """Parse a file node, handling both GenericFile and MediaImage shapes."""
        data = dict(node)
        # MediaImage has nested image object
        image = data.pop("image", None)
        if image and isinstance(image, dict):
            data["image_url"] = image.get("url", "")
            data["image_width"] = image.get("width")
            data["image_height"] = image.get("height")
            if not data.get("url"):
                data["url"] = image.get("url", "")
        return cls.model_validate(data)

    def summary(self) -> dict:
        result: dict = {
            "id": self.id,
            "alt": self.alt,
            "url": self.url or self.image_url or "",
            "status": self.status,
            "mime_type": self.mime_type,
            "created_at": self.created_at,
        }
        if self.original_file_size is not None:
            result["file_size"] = self.original_file_size
        if self.image_width is not None:
            result["width"] = self.image_width
            result["height"] = self.image_height
        return result

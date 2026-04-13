"""Product commands — list, view, create, update, delete, variants, images.

Examples:
    ebshop product list
    ebshop product list --status active --vendor "EarlBear"
    ebshop product view 123456
    ebshop product view my-product-handle
    ebshop product create --title "New Product"
    ebshop product update 123456 --title "Updated"
    ebshop product delete 123456
    ebshop product variants 123456
    ebshop product images 123456
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.product import Product, ProductVariant
from ebshop.output import Format, output_result

product_app = typer.Typer(help="Product management.")

# ── GraphQL fragments ──

_PRODUCT_FIELDS = """
    id
    title
    handle
    status
    vendor
    productType
    tags
    totalInventory
    descriptionHtml
    createdAt
    updatedAt
    featuredImage { url altText width height }
    images(first: 5) { edges { node { url altText width height } } }
    totalVariants
"""

_PRODUCT_LIST_FIELDS = """
    id
    title
    handle
    status
    vendor
    productType
    tags
    totalInventory
    featuredImage { url altText }
    totalVariants
"""

_VARIANT_FIELDS = """
    id
    title
    sku
    price { amount currencyCode }
    compareAtPrice { amount currencyCode }
    inventoryQuantity
    weight
    weightUnit
    barcode
    position
    availableForSale
"""

_IMAGE_FIELDS = """
    url
    altText
    width
    height
"""


# ── Commands ──


@product_app.command("list")
def list_products(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status: active, draft, archived."),
    vendor: str | None = typer.Option(None, "--vendor", help="Filter by vendor name."),
    collection_id: str | None = typer.Option(None, "--collection-id", help="Filter by collection ID."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max products to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List products with optional filters."""
    # Build query string for Shopify search syntax
    query_parts: list[str] = []
    if status:
        query_parts.append(f"status:{status}")
    if vendor:
        query_parts.append(f'vendor:"{vendor}"')
    if collection_id:
        gid = ShopifyClient.to_gid("Collection", collection_id)
        query_parts.append(f'collection_id:"{gid}"')

    query_str = " AND ".join(query_parts) if query_parts else None

    variables: dict = {"first": min(limit, 250)}
    if query_str:
        variables["query"] = query_str

    gql = f"""
        query listProducts($first: Int!, $after: String, $query: String) {{
            products(first: $first, after: $after, query: $query) {{
                edges {{
                    node {{
                        {_PRODUCT_LIST_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """

    client = get_client()
    nodes = client.graphql_paginated(
        gql, variables=variables, connection_path=["products"], max_results=limit,
    )
    products = [Product.from_shopify(n).summary() for n in nodes]
    output_result(
        products, format=format, json_fields=json_fields,
        columns=["id", "title", "handle", "status", "vendor", "total_variants"],
    )


@product_app.command("view")
def view_product(
    id_or_handle: str = typer.Argument(..., help="Product ID (numeric or GID) or handle."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """View detailed product information."""
    client = get_client()

    # Detect handle vs ID: handles are non-numeric and don't start with gid://
    is_handle = not id_or_handle.isdigit() and not id_or_handle.startswith("gid://")

    if is_handle:
        gql = f"""
            query productByHandle($handle: String!) {{
                productByHandle(handle: $handle) {{
                    {_PRODUCT_FIELDS}
                }}
            }}
        """
        data = client.graphql(gql, variables={"handle": id_or_handle})
        node = data.get("productByHandle")
    else:
        gid = ShopifyClient.to_gid("Product", id_or_handle)
        gql = f"""
            query getProduct($id: ID!) {{
                product(id: $id) {{
                    {_PRODUCT_FIELDS}
                }}
            }}
        """
        data = client.graphql(gql, variables={"id": gid})
        node = data.get("product")

    if not node:
        output_result({"error": "NOT_FOUND", "message": f"Product '{id_or_handle}' not found."}, format=format)
        raise typer.Exit(code=1)

    product = Product.from_shopify(node)
    output_result(product.detail(), format=format, json_fields=json_fields)


@product_app.command("create")
def create_product(
    title: str = typer.Option(..., "--title", "-t", help="Product title."),
    description: str | None = typer.Option(None, "--description", "-d", help="Product description (HTML)."),
    vendor: str | None = typer.Option(None, "--vendor", help="Vendor name."),
    product_type: str | None = typer.Option(None, "--product-type", help="Product type."),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags."),
    status: str | None = typer.Option(None, "--status", "-s", help="Status: active or draft."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Create a new product."""
    product_input: dict = {"title": title}
    if description is not None:
        product_input["descriptionHtml"] = description
    if vendor is not None:
        product_input["vendor"] = vendor
    if product_type is not None:
        product_input["productType"] = product_type
    if tags is not None:
        product_input["tags"] = [t.strip() for t in tags.split(",")]
    if status is not None:
        product_input["status"] = status.upper()

    gql = f"""
        mutation productCreate($product: ProductCreateInput!) {{
            productCreate(product: $product) {{
                product {{
                    {_PRODUCT_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"product": product_input})
    node = data.get("productCreate", {}).get("product")
    if not node:
        output_result({"error": "CREATE_FAILED", "message": "Product creation returned no product."}, format=format)
        raise typer.Exit(code=1)

    product = Product.from_shopify(node)
    output_result(product.detail(), format=format, json_fields=json_fields)


@product_app.command("update")
def update_product(
    id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
    title: str | None = typer.Option(None, "--title", "-t", help="New title."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description (HTML)."),
    vendor: str | None = typer.Option(None, "--vendor", help="New vendor."),
    product_type: str | None = typer.Option(None, "--product-type", help="New product type."),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags (replaces all)."),
    status: str | None = typer.Option(None, "--status", "-s", help="New status: active, draft, archived."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Update an existing product."""
    gid = ShopifyClient.to_gid("Product", id)
    product_input: dict = {"id": gid}
    if title is not None:
        product_input["title"] = title
    if description is not None:
        product_input["descriptionHtml"] = description
    if vendor is not None:
        product_input["vendor"] = vendor
    if product_type is not None:
        product_input["productType"] = product_type
    if tags is not None:
        product_input["tags"] = [t.strip() for t in tags.split(",")]
    if status is not None:
        product_input["status"] = status.upper()

    gql = f"""
        mutation productUpdate($product: ProductUpdateInput!) {{
            productUpdate(product: $product) {{
                product {{
                    {_PRODUCT_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"product": product_input})
    node = data.get("productUpdate", {}).get("product")
    if not node:
        output_result({"error": "UPDATE_FAILED", "message": "Product update returned no product."}, format=format)
        raise typer.Exit(code=1)

    product = Product.from_shopify(node)
    output_result(product.detail(), format=format, json_fields=json_fields)


@product_app.command("delete")
def delete_product(
    id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
) -> None:
    """Delete a product."""
    gid = ShopifyClient.to_gid("Product", id)
    gql = """
        mutation productDelete($input: ProductDeleteInput!) {
            productDelete(input: $input) {
                deletedProductId
                userErrors { field message }
            }
        }
    """
    client = get_client()
    data = client.graphql(gql, variables={"input": {"id": gid}})
    deleted_id = data.get("productDelete", {}).get("deletedProductId", "")
    output_result({"deleted": True, "id": deleted_id})


@product_app.command("variants")
def list_variants(
    id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max variants to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List variants for a product."""
    gid = ShopifyClient.to_gid("Product", id)
    gql = f"""
        query productVariants($id: ID!, $first: Int!) {{
            product(id: $id) {{
                variants(first: $first) {{
                    edges {{
                        node {{
                            {_VARIANT_FIELDS}
                        }}
                    }}
                }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid, "first": min(limit, 250)})
    product_data = data.get("product") or {}
    edges = product_data.get("variants", {}).get("edges", [])
    variants = [ProductVariant.from_shopify(e["node"]).summary() for e in edges]
    output_result(
        variants, format=format, json_fields=json_fields,
        columns=["id", "title", "sku", "price", "inventory_quantity"],
    )


@product_app.command("images")
def list_images(
    id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max images to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List images for a product."""
    gid = ShopifyClient.to_gid("Product", id)
    gql = f"""
        query productImages($id: ID!, $first: Int!) {{
            product(id: $id) {{
                images(first: $first) {{
                    edges {{
                        node {{
                            {_IMAGE_FIELDS}
                        }}
                    }}
                }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid, "first": min(limit, 250)})
    product_data = data.get("product") or {}
    edges = product_data.get("images", {}).get("edges", [])
    images = [
        {"url": e["node"].get("url", ""), "alt_text": e["node"].get("altText", ""), "width": e["node"].get("width"), "height": e["node"].get("height")}
        for e in edges
    ]
    output_result(
        images, format=format, json_fields=json_fields,
        columns=["url", "alt_text", "width", "height"],
    )


@product_app.command("attach-image")
def attach_image(
    id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
    url: str = typer.Option(..., "--url", help="Public image URL to attach."),
    alt: str | None = typer.Option(None, "--alt", help="Alt text for the image."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Attach an image to a product from a public URL.

    Uses productCreateMedia to add the image as product media.
    The URL must be publicly accessible (e.g., Google Drive link).

    Examples:
        ebshop product attach-image 123 --url "https://drive.google.com/uc?id=X&export=download"
        ebshop product attach-image 123 --url "https://cdn.example.com/img.jpg" --alt "Product photo"
    """
    gid = ShopifyClient.to_gid("Product", id)
    client = get_client()

    media_input = {
        "originalSource": url,
        "mediaContentType": "IMAGE",
    }
    if alt:
        media_input["alt"] = alt

    gql = """
        mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
            productCreateMedia(productId: $productId, media: $media) {
                media {
                    alt
                    mediaContentType
                    status
                    ... on MediaImage {
                        id
                        image { url width height }
                    }
                }
                mediaUserErrors { field message }
                product { id title }
            }
        }
    """

    data = client.graphql(gql, variables={"productId": gid, "media": [media_input]})
    result = data.get("productCreateMedia", {})
    media = result.get("media", [])
    product = result.get("product", {})

    if media:
        output_result({
            "status": "attached",
            "product_id": product.get("id", ""),
            "product_title": product.get("title", ""),
            "media_count": len(media),
            "media": [{"alt": m.get("alt", ""), "status": m.get("status", "")} for m in media],
        }, format=format, json_fields=json_fields)
    else:
        errors = result.get("mediaUserErrors", [])
        output_result({
            "status": "failed",
            "errors": [e.get("message", "") for e in errors],
        }, format=format)

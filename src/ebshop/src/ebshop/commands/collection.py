"""Collection commands — list, view, create, update, products, add/remove products.

Examples:
    ebshop collection list
    ebshop collection view 123456
    ebshop collection view my-collection-handle
    ebshop collection create --title "Summer Sale"
    ebshop collection update 123456 --title "Winter Sale"
    ebshop collection products 123456
    ebshop collection add-products 123456 --product-ids "111,222,333"
    ebshop collection remove-products 123456 --product-ids "111,222"
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.collection import Collection
from ebshop.output import Format, output_result

collection_app = typer.Typer(help="Collection management.")

# ── GraphQL fragments ──

_COLLECTION_LIST_FIELDS = """
    id
    title
    handle
    sortOrder
    productsCount { count }
    updatedAt
"""

_COLLECTION_FIELDS = """
    id
    title
    handle
    descriptionHtml
    sortOrder
    productsCount { count }
    updatedAt
    image { url altText width height }
"""

_COLLECTION_PRODUCT_FIELDS = """
    id
    title
    handle
    status
"""


# ── Commands ──


@collection_app.command("list")
def list_collections(
    limit: int = typer.Option(50, "--limit", "-n", help="Max collections to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List collections."""
    variables: dict = {"first": min(limit, 250)}

    gql = f"""
        query listCollections($first: Int!, $after: String) {{
            collections(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_COLLECTION_LIST_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """

    client = get_client()
    nodes = client.graphql_paginated(
        gql, variables=variables, connection_path=["collections"], max_results=limit,
    )
    collections = [Collection.from_shopify(n).summary() for n in nodes]
    output_result(
        collections, format=format, json_fields=json_fields,
        columns=["id", "title", "handle", "products_count", "updated_at"],
    )


@collection_app.command("view")
def view_collection(
    id_or_handle: str = typer.Argument(..., help="Collection ID (numeric or GID) or handle."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """View detailed collection information."""
    client = get_client()

    # Detect handle vs ID: handles are non-numeric and don't start with gid://
    is_handle = not id_or_handle.isdigit() and not id_or_handle.startswith("gid://")

    if is_handle:
        gql = f"""
            query collectionByHandle($handle: String!) {{
                collectionByHandle(handle: $handle) {{
                    {_COLLECTION_FIELDS}
                }}
            }}
        """
        data = client.graphql(gql, variables={"handle": id_or_handle})
        node = data.get("collectionByHandle")
    else:
        gid = ShopifyClient.to_gid("Collection", id_or_handle)
        gql = f"""
            query getCollection($id: ID!) {{
                collection(id: $id) {{
                    {_COLLECTION_FIELDS}
                }}
            }}
        """
        data = client.graphql(gql, variables={"id": gid})
        node = data.get("collection")

    if not node:
        output_result({"error": "NOT_FOUND", "message": f"Collection '{id_or_handle}' not found."}, format=format)
        raise typer.Exit(code=1)

    collection = Collection.from_shopify(node)
    output_result(collection.detail(), format=format, json_fields=json_fields)


@collection_app.command("create")
def create_collection(
    title: str = typer.Option(..., "--title", "-t", help="Collection title."),
    description: str | None = typer.Option(None, "--description", "-d", help="Collection description (HTML)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Create a new manual collection."""
    collection_input: dict = {"title": title}
    if description is not None:
        collection_input["descriptionHtml"] = description

    gql = f"""
        mutation collectionCreate($input: CollectionInput!) {{
            collectionCreate(input: $input) {{
                collection {{
                    {_COLLECTION_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"input": collection_input})
    node = data.get("collectionCreate", {}).get("collection")
    if not node:
        output_result({"error": "CREATE_FAILED", "message": "Collection creation returned no collection."}, format=format)
        raise typer.Exit(code=1)

    collection = Collection.from_shopify(node)
    output_result(collection.detail(), format=format, json_fields=json_fields)


@collection_app.command("update")
def update_collection(
    id: str = typer.Argument(..., help="Collection ID (numeric or GID)."),
    title: str | None = typer.Option(None, "--title", "-t", help="New title."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description (HTML)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Update an existing collection."""
    gid = ShopifyClient.to_gid("Collection", id)
    collection_input: dict = {"id": gid}
    if title is not None:
        collection_input["title"] = title
    if description is not None:
        collection_input["descriptionHtml"] = description

    gql = f"""
        mutation collectionUpdate($input: CollectionInput!) {{
            collectionUpdate(input: $input) {{
                collection {{
                    {_COLLECTION_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"input": collection_input})
    node = data.get("collectionUpdate", {}).get("collection")
    if not node:
        output_result({"error": "UPDATE_FAILED", "message": "Collection update returned no collection."}, format=format)
        raise typer.Exit(code=1)

    collection = Collection.from_shopify(node)
    output_result(collection.detail(), format=format, json_fields=json_fields)


@collection_app.command("products")
def list_products(
    id: str = typer.Argument(..., help="Collection ID (numeric or GID)."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max products to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List products in a collection."""
    gid = ShopifyClient.to_gid("Collection", id)
    gql = f"""
        query collectionProducts($id: ID!, $first: Int!) {{
            collection(id: $id) {{
                products(first: $first) {{
                    edges {{
                        node {{
                            {_COLLECTION_PRODUCT_FIELDS}
                        }}
                    }}
                }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid, "first": min(limit, 250)})
    collection_data = data.get("collection") or {}
    edges = collection_data.get("products", {}).get("edges", [])
    products = [
        {
            "id": e["node"].get("id", ""),
            "title": e["node"].get("title", ""),
            "handle": e["node"].get("handle", ""),
            "status": e["node"].get("status", ""),
        }
        for e in edges
    ]
    output_result(
        products, format=format, json_fields=json_fields,
        columns=["id", "title", "handle", "status"],
    )


@collection_app.command("add-products")
def add_products(
    id: str = typer.Argument(..., help="Collection ID (numeric or GID)."),
    product_ids: str = typer.Option(..., "--product-ids", help="Comma-separated product IDs to add."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Add products to a collection."""
    gid = ShopifyClient.to_gid("Collection", id)
    pids = [ShopifyClient.to_gid("Product", p.strip()) for p in product_ids.split(",")]

    gql = f"""
        mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {{
            collectionAddProducts(id: $id, productIds: $productIds) {{
                collection {{
                    {_COLLECTION_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid, "productIds": pids})
    node = data.get("collectionAddProducts", {}).get("collection")
    if not node:
        output_result({"error": "ADD_FAILED", "message": "Failed to add products to collection."}, format=format)
        raise typer.Exit(code=1)

    collection = Collection.from_shopify(node)
    output_result(collection.detail(), format=format, json_fields=json_fields)


@collection_app.command("remove-products")
def remove_products(
    id: str = typer.Argument(..., help="Collection ID (numeric or GID)."),
    product_ids: str = typer.Option(..., "--product-ids", help="Comma-separated product IDs to remove."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(None, "--json", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Remove products from a collection."""
    gid = ShopifyClient.to_gid("Collection", id)
    pids = [ShopifyClient.to_gid("Product", p.strip()) for p in product_ids.split(",")]

    gql = f"""
        mutation collectionRemoveProducts($id: ID!, $productIds: [ID!]!) {{
            collectionRemoveProducts(id: $id, productIds: $productIds) {{
                collection {{
                    {_COLLECTION_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid, "productIds": pids})
    node = data.get("collectionRemoveProducts", {}).get("collection")
    if not node:
        output_result({"error": "REMOVE_FAILED", "message": "Failed to remove products from collection."}, format=format)
        raise typer.Exit(code=1)

    collection = Collection.from_shopify(node)
    output_result(collection.detail(), format=format, json_fields=json_fields)

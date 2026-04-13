"""Metafield commands — list, get, set, delete.

Examples:
    ebshop metafield list --owner-type product --owner-id 123456
    ebshop metafield list --owner-type shop
    ebshop metafield get gid://shopify/Metafield/123
    ebshop metafield set --owner-id 123 --namespace custom --key color --value blue --type single_line_text_field
    ebshop metafield delete gid://shopify/Metafield/123
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.metafield import Metafield
from ebshop.output import Format, output_result

metafield_app = typer.Typer(help="Metafield management.")

# ── GraphQL fragments ──

_METAFIELD_FIELDS = """
    id
    namespace
    key
    value
    type
"""

_METAFIELD_DETAIL_FIELDS = """
    id
    namespace
    key
    value
    type
    createdAt
    updatedAt
    ownerType
"""

# ── Owner type mapping ──

_OWNER_TYPE_MAP = {
    "product": "Product",
    "order": "Order",
    "customer": "Customer",
    "collection": "Collection",
}


@metafield_app.command("list")
def list_metafields(
    owner_type: str = typer.Option(
        ..., "--owner-type", help="Owner type: product, order, customer, collection, or shop.",
    ),
    owner_id: str | None = typer.Option(
        None, "--owner-id", help="Owner ID (not required for shop).",
    ),
    namespace: str | None = typer.Option(
        None, "--namespace", help="Filter by namespace.",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output.",
    ),
) -> None:
    """List metafields for a resource."""
    client = get_client()
    owner_type_lower = owner_type.lower()

    if owner_type_lower == "shop":
        data = _list_shop_metafields(client, limit=limit, namespace=namespace)
    else:
        if not owner_id:
            output_result(
                {"error": "MISSING_OWNER_ID", "message": "--owner-id is required for non-shop owner types."},
                format=format, json_fields=json_fields,
            )
            raise typer.Exit(code=1)
        resource = _OWNER_TYPE_MAP.get(owner_type_lower)
        if not resource:
            output_result(
                {"error": "INVALID_OWNER_TYPE", "message": f"Unknown owner type: {owner_type}. Use product, order, customer, collection, or shop."},
                format=format, json_fields=json_fields,
            )
            raise typer.Exit(code=1)
        data = _list_resource_metafields(client, resource=resource, owner_id=owner_id, limit=limit, namespace=namespace)

    metafields = [Metafield.from_shopify(node).summary() for node in data]
    output_result(
        metafields, format=format, json_fields=json_fields,
        columns=["id", "namespace", "key", "value", "type"],
    )


def _list_shop_metafields(
    client: ShopifyClient, *, limit: int, namespace: str | None,
) -> list[dict]:
    """Fetch metafields from the shop resource."""
    ns_arg = ', namespace: $namespace' if namespace else ''
    ns_var = ', $namespace: String' if namespace else ''
    query = f"""
        query($first: Int!{ns_var}) {{
            shop {{
                metafields(first: $first{ns_arg}) {{
                    edges {{ node {{ {_METAFIELD_FIELDS} }} }}
                }}
            }}
        }}
    """
    variables: dict = {"first": limit}
    if namespace:
        variables["namespace"] = namespace
    data = client.graphql(query, variables)
    edges = data.get("shop", {}).get("metafields", {}).get("edges", [])
    return [e["node"] for e in edges]


def _list_resource_metafields(
    client: ShopifyClient,
    *,
    resource: str,
    owner_id: str,
    limit: int,
    namespace: str | None,
) -> list[dict]:
    """Fetch metafields from a product/order/customer/collection."""
    resource_lower = resource.lower()
    gid = client.to_gid(resource, owner_id)
    ns_arg = ', namespace: $namespace' if namespace else ''
    ns_var = ', $namespace: String' if namespace else ''
    query = f"""
        query($ownerId: ID!, $first: Int!{ns_var}) {{
            {resource_lower}(id: $ownerId) {{
                metafields(first: $first{ns_arg}) {{
                    edges {{ node {{ {_METAFIELD_FIELDS} }} }}
                }}
            }}
        }}
    """
    variables: dict = {"ownerId": gid, "first": limit}
    if namespace:
        variables["namespace"] = namespace
    data = client.graphql(query, variables)
    edges = data.get(resource_lower, {}).get("metafields", {}).get("edges", [])
    return [e["node"] for e in edges]


@metafield_app.command("get")
def get_metafield(
    id: str = typer.Argument(help="Metafield GID or numeric ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output.",
    ),
) -> None:
    """Get a single metafield by ID."""
    client = get_client()
    gid = client.to_gid("Metafield", id)
    query = f"""
        query($id: ID!) {{
            node(id: $id) {{
                ... on Metafield {{ {_METAFIELD_DETAIL_FIELDS} }}
            }}
        }}
    """
    data = client.graphql(query, {"id": gid})
    node = data.get("node", {})
    metafield = Metafield.from_shopify(node)
    output_result(metafield.detail(), format=format, json_fields=json_fields)


@metafield_app.command("set")
def set_metafield(
    owner_id: str = typer.Option(..., "--owner-id", help="Owner GID or numeric ID (use Product/Order/etc. prefix)."),
    namespace: str = typer.Option(..., "--namespace", help="Metafield namespace."),
    key: str = typer.Option(..., "--key", help="Metafield key."),
    value: str = typer.Option(..., "--value", help="Metafield value."),
    type: str = typer.Option(
        ..., "--type",
        help="Metafield type: single_line_text_field, number_integer, json, boolean.",
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output.",
    ),
) -> None:
    """Set (create or update) a metafield on a resource."""
    client = get_client()
    # owner_id should already be a GID or we use it raw (the mutation accepts GIDs)
    if not owner_id.startswith("gid://"):
        # Assume product if no prefix — caller should pass full GID
        owner_id = f"gid://shopify/Product/{owner_id}"
    query = f"""
        mutation($metafields: [MetafieldsSetInput!]!) {{
            metafieldsSet(metafields: $metafields) {{
                metafields {{ {_METAFIELD_DETAIL_FIELDS} }}
                userErrors {{ field message }}
            }}
        }}
    """
    variables = {
        "metafields": [{
            "ownerId": owner_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "type": type,
        }],
    }
    data = client.graphql(query, variables)
    metafields_data = data.get("metafieldsSet", {}).get("metafields", [])
    if metafields_data:
        metafield = Metafield.from_shopify(metafields_data[0])
        output_result(metafield.detail(), format=format, json_fields=json_fields)
    else:
        output_result({"status": "ok", "message": "Metafield set."}, format=format, json_fields=json_fields)


@metafield_app.command("delete")
def delete_metafield(
    id: str = typer.Argument(help="Metafield GID or numeric ID."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output.",
    ),
) -> None:
    """Delete a metafield by ID."""
    client = get_client()
    gid = client.to_gid("Metafield", id)
    query = """
        mutation($input: MetafieldDeleteInput!) {
            metafieldDelete(input: $input) {
                deletedId
                userErrors { field message }
            }
        }
    """
    data = client.graphql(query, {"input": {"id": gid}})
    deleted_id = data.get("metafieldDelete", {}).get("deletedId", "")
    output_result(
        {"deleted_id": deleted_id, "status": "ok"},
        format=format, json_fields=json_fields,
    )

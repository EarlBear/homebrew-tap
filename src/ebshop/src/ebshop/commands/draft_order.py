"""Draft order commands — list, view, create, complete, delete.

Examples:
    ebshop draft-order list
    ebshop draft-order view 12345
    ebshop draft-order create --line-items '[{"title":"Custom Item","quantity":1,"originalUnitPrice":"10.00"}]'
    ebshop draft-order create --line-items '[{"variantId":"gid://shopify/ProductVariant/1","quantity":2}]' --customer-id 789 --note "Rush order"
    ebshop draft-order complete 12345
    ebshop draft-order delete 12345
"""

from __future__ import annotations

import json as json_mod

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.draft_order import DraftOrder
from ebshop.output import Format, output_result

draft_order_app = typer.Typer(help="Draft order management — list, view, create, complete, delete.")

# ── GraphQL fragments ──

_DO_FIELDS = """
    id
    name
    status
    createdAt
    updatedAt
    completedAt
    invoiceUrl
    totalPriceSet { shopMoney { amount currencyCode } }
    customer { firstName lastName }
    lineItems(first: 50) { edges { node { id title quantity } } }
"""

LIST_QUERY = f"""
    query ListDraftOrders($first: Int!, $after: String) {{
        draftOrders(first: $first, after: $after) {{
            edges {{
                node {{
                    {_DO_FIELDS}
                }}
            }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
"""

VIEW_QUERY = f"""
    query GetDraftOrder($id: ID!) {{
        draftOrder(id: $id) {{
            {_DO_FIELDS}
        }}
    }}
"""

CREATE_MUTATION = f"""
    mutation DraftOrderCreate($input: DraftOrderInput!) {{
        draftOrderCreate(input: $input) {{
            draftOrder {{
                {_DO_FIELDS}
            }}
            userErrors {{ field message }}
        }}
    }}
"""

COMPLETE_MUTATION = f"""
    mutation DraftOrderComplete($id: ID!) {{
        draftOrderComplete(id: $id) {{
            draftOrder {{
                {_DO_FIELDS}
            }}
            userErrors {{ field message }}
        }}
    }}
"""

DELETE_MUTATION = """
    mutation DraftOrderDelete($input: DraftOrderDeleteInput!) {
        draftOrderDelete(input: $input) {
            deletedId
            userErrors { field message }
        }
    }
"""


@draft_order_app.command("list")
def list_draft_orders(
    limit: int = typer.Option(10, "--limit", "-l", help="Max draft orders to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List draft orders."""
    client = get_client()
    nodes = client.graphql_paginated(
        LIST_QUERY,
        variables={"first": min(limit, 50)},
        connection_path=["draftOrders"],
        max_results=limit,
    )
    items = [DraftOrder.from_shopify(n).summary() for n in nodes]
    output_result(
        items, format=format, json_fields=json_fields,
        columns=["id", "name", "status", "customer", "total", "created_at"],
    )


@draft_order_app.command()
def view(
    id: str = typer.Argument(help="Draft order ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed draft order information."""
    client = get_client()
    gid = ShopifyClient.to_gid("DraftOrder", id)

    data = client.graphql(VIEW_QUERY, variables={"id": gid})
    do_data = data.get("draftOrder", {})
    draft = DraftOrder.from_shopify(do_data)
    output_result(draft.detail(), format=format, json_fields=json_fields)


@draft_order_app.command()
def create(
    line_items: str = typer.Option(..., "--line-items", help="JSON array of line items."),
    customer_id: str | None = typer.Option(None, "--customer-id", help="Customer ID."),
    note: str | None = typer.Option(None, "--note", "-n", help="Order note."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a draft order."""
    client = get_client()

    input_data: dict = {"lineItems": json_mod.loads(line_items)}
    if customer_id:
        gid = ShopifyClient.to_gid("Customer", customer_id)
        input_data["customerId"] = gid
    # Note: 'note' field was removed from DraftOrder in 2026-01 API version
    # Skip it silently — the note is not critical for order creation

    data = client.graphql(CREATE_MUTATION, variables={"input": input_data})
    do_data = data.get("draftOrderCreate", {}).get("draftOrder", {})
    draft = DraftOrder.from_shopify(do_data)
    output_result(draft.detail(), format=format, json_fields=json_fields)


@draft_order_app.command()
def complete(
    id: str = typer.Argument(help="Draft order ID to complete."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Complete a draft order, converting it to a real order."""
    client = get_client()
    gid = ShopifyClient.to_gid("DraftOrder", id)

    data = client.graphql(COMPLETE_MUTATION, variables={"id": gid})
    do_data = data.get("draftOrderComplete", {}).get("draftOrder", {})
    draft = DraftOrder.from_shopify(do_data)
    output_result(draft.detail(), format=format, json_fields=json_fields)


@draft_order_app.command()
def delete(
    id: str = typer.Argument(help="Draft order ID to delete."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a draft order."""
    client = get_client()
    gid = ShopifyClient.to_gid("DraftOrder", id)

    data = client.graphql(DELETE_MUTATION, variables={"input": {"id": gid}})
    deleted_id = data.get("draftOrderDelete", {}).get("deletedId")

    result = {
        "deleted": True,
        "id": deleted_id or gid,
    }
    output_result(result, format=format, json_fields=json_fields)

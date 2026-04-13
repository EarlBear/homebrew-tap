"""Return commands — list, view, create.

Examples:
    ebshop return list
    ebshop return list --limit 5
    ebshop return view gid://shopify/Return/123
    ebshop return create --order-id 12345 --line-items '[{"fulfillmentLineItemId":"gid://shopify/FulfillmentLineItem/1","quantity":1,"returnReason":"SIZE_TOO_SMALL"}]'
"""

from __future__ import annotations

import json as json_mod

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.return_ import Return
from ebshop.output import Format, output_result

return_app = typer.Typer(help="Return management — list, view, create.")

# ── GraphQL fragments ──

_RETURN_FIELDS = """
    id
    status
    name
    createdAt
    updatedAt
    declineReason
    order { id }
    returnLineItems(first: 50) {
        edges { node { id quantity } }
    }
"""

LIST_QUERY = f"""
    query ListReturns($first: Int!, $after: String) {{
        returns(first: $first, after: $after) {{
            edges {{
                node {{
                    {_RETURN_FIELDS}
                }}
            }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
"""

VIEW_QUERY = f"""
    query GetReturn($id: ID!) {{
        return_(id: $id) {{
            {_RETURN_FIELDS}
        }}
    }}
"""

CREATE_MUTATION = f"""
    mutation ReturnCreate($input: ReturnInput!) {{
        returnCreate(returnInput: $input) {{
            return_ {{
                {_RETURN_FIELDS}
            }}
            userErrors {{ field message }}
        }}
    }}
"""


@return_app.command("list")
def list_returns(
    limit: int = typer.Option(10, "--limit", "-l", help="Max returns to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List returns."""
    client = get_client()
    nodes = client.graphql_paginated(
        LIST_QUERY,
        variables={"first": min(limit, 50)},
        connection_path=["returns"],
        max_results=limit,
    )
    items = [Return.from_shopify(n).summary() for n in nodes]
    output_result(
        items, format=format, json_fields=json_fields,
        columns=["id", "status", "name", "order_id", "total_quantity", "created_at"],
    )


@return_app.command()
def view(
    id: str = typer.Argument(help="Return ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed return information."""
    client = get_client()
    gid = ShopifyClient.to_gid("Return", id)

    data = client.graphql(VIEW_QUERY, variables={"id": gid})
    return_data = data.get("return_", {})
    ret = Return.from_shopify(return_data)
    output_result(ret.detail(), format=format, json_fields=json_fields)


@return_app.command()
def create(
    order_id: str = typer.Option(..., "--order-id", help="Order ID to create return for."),
    line_items: str | None = typer.Option(
        None, "--line-items", help="JSON array of return line items."
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a return for an order."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", order_id)

    input_data: dict = {"orderId": gid}
    if line_items:
        input_data["returnLineItems"] = json_mod.loads(line_items)

    data = client.graphql(CREATE_MUTATION, variables={"input": input_data})
    return_data = data.get("returnCreate", {}).get("return_", {})
    ret = Return.from_shopify(return_data)
    output_result(ret.detail(), format=format, json_fields=json_fields)

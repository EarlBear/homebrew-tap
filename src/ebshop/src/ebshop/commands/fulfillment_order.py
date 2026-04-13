"""Fulfillment order commands — list, accept, reject.

Examples:
    ebshop fulfillment-order list 12345
    ebshop fulfillment-order accept gid://shopify/FulfillmentOrder/1
    ebshop fulfillment-order reject gid://shopify/FulfillmentOrder/1 --reason "Out of stock"
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.fulfillment_order import FulfillmentOrder
from ebshop.output import Format, output_result

fulfillment_order_app = typer.Typer(help="Fulfillment order workflow — list, accept, reject.")

# ── GraphQL fragments ──

_FO_FIELDS = """
    id
    status
    requestStatus
    createdAt
    updatedAt
    orderId
    assignedLocation { name }
    lineItems(first: 10) { edges { node { id totalQuantity } } }
"""

LIST_QUERY = f"""
    query FulfillmentOrders($id: ID!) {{
        order(id: $id) {{
            fulfillmentOrders(first: 10) {{
                edges {{
                    node {{
                        {_FO_FIELDS}
                    }}
                }}
            }}
        }}
    }}
"""

ACCEPT_MUTATION = f"""
    mutation AcceptFulfillment($id: ID!, $message: String) {{
        fulfillmentOrderAcceptFulfillmentRequest(id: $id, message: $message) {{
            fulfillmentOrder {{
                {_FO_FIELDS}
            }}
            userErrors {{ field message }}
        }}
    }}
"""

REJECT_MUTATION = f"""
    mutation RejectFulfillment($id: ID!, $reason: FulfillmentOrderRejectionReason, $message: String) {{
        fulfillmentOrderRejectFulfillmentRequest(id: $id, reason: $reason, message: $message) {{
            fulfillmentOrder {{
                {_FO_FIELDS}
            }}
            userErrors {{ field message }}
        }}
    }}
"""


@fulfillment_order_app.command("list")
def list_fulfillment_orders(
    order_id: str = typer.Argument(help="Order ID (numeric or GID) to list fulfillment orders for."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List fulfillment orders for a given order."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", order_id)

    data = client.graphql(LIST_QUERY, variables={"id": gid})
    order_data = data.get("order", {})
    edges = order_data.get("fulfillmentOrders", {}).get("edges", [])

    items = [FulfillmentOrder.from_shopify(e["node"]).summary() for e in edges]
    output_result(
        items, format=format, json_fields=json_fields,
        columns=["id", "status", "request_status", "assigned_location", "created_at"],
    )


@fulfillment_order_app.command()
def accept(
    id: str = typer.Argument(help="Fulfillment order ID (numeric or GID)."),
    message: str | None = typer.Option(None, "--message", "-m", help="Optional acceptance message."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Accept a fulfillment request."""
    client = get_client()
    gid = ShopifyClient.to_gid("FulfillmentOrder", id)

    variables: dict = {"id": gid}
    if message:
        variables["message"] = message

    data = client.graphql(ACCEPT_MUTATION, variables=variables)
    fo_data = data.get("fulfillmentOrderAcceptFulfillmentRequest", {}).get("fulfillmentOrder", {})

    result = FulfillmentOrder.from_shopify(fo_data).summary()
    result["action"] = "accepted"
    output_result(result, format=format, json_fields=json_fields)


@fulfillment_order_app.command()
def reject(
    id: str = typer.Argument(help="Fulfillment order ID (numeric or GID)."),
    reason: str | None = typer.Option(None, "--reason", "-r", help="Rejection reason."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Reject a fulfillment request."""
    client = get_client()
    gid = ShopifyClient.to_gid("FulfillmentOrder", id)

    variables: dict = {"id": gid}
    if reason:
        variables["reason"] = "OTHER"
        variables["message"] = reason

    data = client.graphql(REJECT_MUTATION, variables=variables)
    fo_data = data.get("fulfillmentOrderRejectFulfillmentRequest", {}).get("fulfillmentOrder", {})

    result = FulfillmentOrder.from_shopify(fo_data).summary()
    result["action"] = "rejected"
    if reason:
        result["rejection_reason"] = reason
    output_result(result, format=format, json_fields=json_fields)

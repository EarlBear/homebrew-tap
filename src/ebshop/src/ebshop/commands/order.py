"""Order commands — list, view, fulfill, cancel, and notes.

Examples:
    ebshop order list
    ebshop order list --status open --financial-status paid
    ebshop order view 12345
    ebshop order fulfill 12345 --tracking-number ABC123 --notify
    ebshop order cancel 12345 --reason "Customer request" --refund --restock
    ebshop order notes 12345
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.order import Order
from ebshop.output import Format, output_result

order_app = typer.Typer(help="Order management — list, view, fulfill, cancel, notes.")

# ── GraphQL fragments ──

ORDER_FIELDS = """
    id
    name
    email
    phone
    createdAt
    updatedAt
    cancelledAt
    closedAt
    displayFinancialStatus
    displayFulfillmentStatus
    currencyCode
    note
    tags
    totalPriceSet { shopMoney { amount currencyCode } }
    subtotalPriceSet { shopMoney { amount currencyCode } }
    totalTaxSet { shopMoney { amount currencyCode } }
    customer { firstName lastName }
    shippingAddress {
        address1 address2 city province country zip
    }
    lineItems(first: 50) {
        edges {
            node {
                id title quantity variantTitle sku
                originalTotalSet { shopMoney { amount currencyCode } }
            }
        }
    }
"""

LIST_QUERY = f"""
    query ListOrders($first: Int!, $after: String, $query: String) {{
        orders(first: $first, after: $after, query: $query) {{
            edges {{ node {{ {ORDER_FIELDS} }} }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
"""


VIEW_QUERY = f"""
    query GetOrder($id: ID!) {{
        order(id: $id) {{ {ORDER_FIELDS} }}
    }}
"""

FULFILL_MUTATION = """
    mutation FulfillmentCreate($fulfillment: FulfillmentV2Input!) {
        fulfillmentCreateV2(fulfillment: $fulfillment) {
            fulfillment {
                id
                status
                trackingInfo { number company url }
            }
            userErrors { field message }
        }
    }
"""

CANCEL_MUTATION = """
    mutation OrderCancel($orderId: ID!, $reason: OrderCancelReason!, $refund: Boolean!, $restock: Boolean!) {
        orderCancel(orderId: $orderId, reason: $reason, refund: $refund, restock: $restock) {
            job { id done }
            orderCancelUserErrors { field message code }
            userErrors { field message }
        }
    }
"""

NOTES_QUERY = """
    query OrderEvents($id: ID!, $first: Int!) {
        order(id: $id) {
            events(first: $first) {
                edges {
                    node {
                        id
                        createdAt
                        message
                        ... on CommentEvent {
                            message
                            author { name }
                        }
                    }
                }
            }
        }
    }
"""


@order_app.command("list")
def list_orders(
    status: str | None = typer.Option(
        None, "--status", "-s", help="Filter by status: open, closed, cancelled."
    ),
    financial_status: str | None = typer.Option(
        None, "--financial-status", help="Filter by financial status: paid, pending, refunded, authorized."
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="Max orders to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List orders with optional status and financial status filters."""
    client = get_client()

    # Build query string for Shopify search
    query_parts: list[str] = []
    if status:
        query_parts.append(f"status:{status}")
    if financial_status:
        query_parts.append(f"financial_status:{financial_status}")
    query_str = " ".join(query_parts) if query_parts else None

    variables: dict = {"first": min(limit, 250)}
    if query_str:
        variables["query"] = query_str

    nodes = client.graphql_paginated(
        LIST_QUERY,
        variables=variables,
        connection_path=["orders"],
        max_results=limit,
    )

    orders = [Order.from_shopify(n).to_summary() for n in nodes]
    output_result(
        orders, format=format, json_fields=json_fields,
        columns=["name", "customer", "financial_status", "fulfillment_status", "total", "created_at"],
    )


@order_app.command()
def view(
    id_or_number: str = typer.Argument(help="Order ID or order number."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed order information by ID or order number."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", id_or_number)
    data = client.graphql(VIEW_QUERY, variables={"id": gid})
    order_data = data.get("order", {})
    order = Order.from_shopify(order_data)
    output_result(order.to_detail(), format=format, json_fields=json_fields)


@order_app.command()
def fulfill(
    id: str = typer.Argument(help="Order ID to fulfill."),
    tracking_number: str | None = typer.Option(
        None, "--tracking-number", "-t", help="Tracking number."
    ),
    tracking_company: str | None = typer.Option(
        None, "--tracking-company", "-c", help="Tracking company name."
    ),
    notify: bool = typer.Option(False, "--notify", "-n", help="Notify customer of fulfillment."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a fulfillment for an order."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", id)

    fulfillment_input: dict = {
        "orderId": gid,
        "notifyCustomer": notify,
    }
    if tracking_number or tracking_company:
        tracking: dict = {}
        if tracking_number:
            tracking["number"] = tracking_number
        if tracking_company:
            tracking["company"] = tracking_company
        fulfillment_input["trackingInfo"] = tracking

    data = client.graphql(FULFILL_MUTATION, variables={"fulfillment": fulfillment_input})
    fulfillment = data.get("fulfillmentCreateV2", {}).get("fulfillment", {})

    result = {
        "id": fulfillment.get("id", ""),
        "status": fulfillment.get("status", ""),
        "tracking": fulfillment.get("trackingInfo", []),
    }
    output_result(result, format=format, json_fields=json_fields)


@order_app.command()
def cancel(
    id: str = typer.Argument(help="Order ID to cancel."),
    reason: str = typer.Option(
        "OTHER", "--reason", "-r", help="Cancellation reason (CUSTOMER, DECLINED, FRAUD, INVENTORY, OTHER)."
    ),
    refund: bool = typer.Option(False, "--refund", help="Issue a refund."),
    restock: bool = typer.Option(False, "--restock", help="Restock cancelled items."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Cancel an order with optional refund and restock."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", id)

    data = client.graphql(
        CANCEL_MUTATION,
        variables={
            "orderId": gid,
            "reason": reason.upper(),
            "refund": refund,
            "restock": restock,
        },
    )
    cancel_data = data.get("orderCancel", {})
    job = cancel_data.get("job", {})

    result = {
        "order_id": gid,
        "reason": reason.upper(),
        "refund": refund,
        "restock": restock,
        "job_id": job.get("id", ""),
        "done": job.get("done", False),
    }
    output_result(result, format=format, json_fields=json_fields)


@order_app.command()
def notes(
    id: str = typer.Argument(help="Order ID to fetch notes/events for."),
    limit: int = typer.Option(20, "--limit", "-l", help="Max events to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List order events and notes."""
    client = get_client()
    gid = ShopifyClient.to_gid("Order", id)

    data = client.graphql(NOTES_QUERY, variables={"id": gid, "first": limit})
    order_data = data.get("order", {})
    event_edges = order_data.get("events", {}).get("edges", [])

    events = []
    for edge in event_edges:
        node = edge.get("node", {})
        events.append({
            "id": node.get("id", ""),
            "created_at": node.get("createdAt", ""),
            "message": node.get("message", ""),
            "author": node.get("author", {}).get("name", "") if node.get("author") else "",
        })

    output_result(
        events, format=format, json_fields=json_fields,
        columns=["id", "created_at", "message", "author"],
    )

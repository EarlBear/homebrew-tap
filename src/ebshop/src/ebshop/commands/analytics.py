"""Analytics commands — sales summary, top products, top customers.

Computes stats from order data via GraphQL.

Examples:
    ebshop analytics summary
    ebshop analytics summary --days 7
    ebshop analytics top-products --days 30 --limit 5
    ebshop analytics top-customers --days 30 --limit 10
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import typer

from ebshop.client import get_client
from ebshop.models.analytics import SalesSummary, TopCustomer, TopProduct
from ebshop.output import Format, output_result

analytics_app = typer.Typer(help="Sales analytics computed from order data.")

ORDERS_QUERY = """
query($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id name createdAt
        displayFinancialStatus displayFulfillmentStatus
        totalPriceSet { shopMoney { amount currencyCode } }
        lineItems(first: 50) { edges { node { title quantity sku
          originalTotalSet { shopMoney { amount currencyCode } }
        } } }
        customer { id firstName lastName email }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def _fetch_orders(days: int) -> list[dict]:
    """Fetch recent orders within the given day range."""
    client = get_client()
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return client.graphql_paginated(
        ORDERS_QUERY,
        variables={"first": 250, "query": f"created_at:>{since}"},
        connection_path=["orders"],
        max_results=250,
    )


def _order_total(order: dict) -> tuple[float, str]:
    """Extract total amount and currency from an order node."""
    money = order.get("totalPriceSet", {}).get("shopMoney", {})
    amount = float(money.get("amount", "0"))
    currency = money.get("currencyCode", "USD")
    return amount, currency


@analytics_app.command()
def summary(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to look back."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Sales summary: orders, revenue, AOV, customers, fulfillment rate."""
    orders = _fetch_orders(days)

    total_revenue = 0.0
    currency = "USD"
    emails: set[str] = set()
    fulfilled = 0

    for order in orders:
        amount, cur = _order_total(order)
        total_revenue += amount
        currency = cur

        customer = order.get("customer") or {}
        email = customer.get("email", "")
        if email:
            emails.add(email)

        if order.get("displayFulfillmentStatus") == "FULFILLED":
            fulfilled += 1

    total_orders = len(orders)
    aov = total_revenue / total_orders if total_orders else 0.0
    fulfillment_rate = (fulfilled / total_orders * 100) if total_orders else 0.0

    result = SalesSummary(
        period_days=days,
        total_orders=total_orders,
        total_revenue=total_revenue,
        currency=currency,
        average_order_value=aov,
        unique_customers=len(emails),
        fulfillment_rate=fulfillment_rate,
    )
    output_result(result.to_dict(), format=format, json_fields=json_fields)


@analytics_app.command("top-products")
def top_products(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to look back."),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of products to show."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Top products by units sold."""
    orders = _fetch_orders(days)

    products: dict[str, dict] = defaultdict(lambda: {"units_sold": 0, "revenue": 0.0, "currency": "USD"})

    for order in orders:
        line_edges = order.get("lineItems", {}).get("edges", [])
        for edge in line_edges:
            node = edge["node"]
            title = node.get("title", "Unknown")
            quantity = node.get("quantity", 0)
            money = node.get("originalTotalSet", {}).get("shopMoney", {})
            amount = float(money.get("amount", "0"))
            currency = money.get("currencyCode", "USD")
            products[title]["units_sold"] += quantity
            products[title]["revenue"] += amount
            products[title]["currency"] = currency

    sorted_products = sorted(products.items(), key=lambda x: x[1]["units_sold"], reverse=True)[:limit]

    result = [
        TopProduct(
            rank=i + 1,
            title=title,
            units_sold=data["units_sold"],
            revenue=data["revenue"],
            currency=data["currency"],
        ).to_dict()
        for i, (title, data) in enumerate(sorted_products)
    ]
    output_result(result, format=format, json_fields=json_fields,
                  columns=["rank", "title", "units_sold", "revenue", "currency"])


@analytics_app.command("top-customers")
def top_customers(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to look back."),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of customers to show."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Top customers by total spend."""
    orders = _fetch_orders(days)

    customers: dict[str, dict] = defaultdict(
        lambda: {"name": "", "orders_count": 0, "total_spent": 0.0, "currency": "USD"}
    )

    for order in orders:
        customer = order.get("customer") or {}
        email = customer.get("email", "")
        if not email:
            continue

        first = customer.get("firstName", "") or ""
        last = customer.get("lastName", "") or ""
        name = f"{first} {last}".strip()

        amount, currency = _order_total(order)
        customers[email]["name"] = name or customers[email]["name"]
        customers[email]["orders_count"] += 1
        customers[email]["total_spent"] += amount
        customers[email]["currency"] = currency

    sorted_customers = sorted(customers.items(), key=lambda x: x[1]["total_spent"], reverse=True)[:limit]

    result = [
        TopCustomer(
            rank=i + 1,
            name=data["name"],
            email=email,
            orders_count=data["orders_count"],
            total_spent=data["total_spent"],
            currency=data["currency"],
        ).to_dict()
        for i, (email, data) in enumerate(sorted_customers)
    ]
    output_result(result, format=format, json_fields=json_fields,
                  columns=["rank", "name", "email", "orders_count", "total_spent", "currency"])

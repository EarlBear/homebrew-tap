"""Discount commands — list, view, create, delete.

Examples:
    ebshop discount list
    ebshop discount list --limit 10
    ebshop discount view 123456
    ebshop discount create --title "10% Off" --type percentage --value 10
    ebshop discount create --title "$5 Off" --type fixed_amount --value 5 --code SAVE5
    ebshop discount delete 123456
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.discount import Discount
from ebshop.output import Format, output_result

discount_app = typer.Typer(help="Discount management.")

# ── GraphQL fragments ──

_DISCOUNT_FIELDS = """
    ... on DiscountCodeBasic {
        title
        status
        startsAt
        endsAt
        usageCount: asyncUsageCount
        codes(first: 1) { edges { node { code } } }
        customerGets {
            value {
                ... on DiscountPercentage { percentage }
                ... on DiscountAmount { amount { amount currencyCode } }
            }
            items { ... on AllDiscountItems { allItems } }
        }
    }
    ... on DiscountAutomaticBasic {
        title
        status
        startsAt
        endsAt
        customerGets {
            value {
                ... on DiscountPercentage { percentage }
                ... on DiscountAmount { amount { amount currencyCode } }
            }
            items { ... on AllDiscountItems { allItems } }
        }
    }
"""


# ── Commands ──


@discount_app.command("list")
def list_discounts(
    limit: int = typer.Option(50, "--limit", "-n", help="Max discounts to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List discounts (code-based and automatic)."""
    gql = f"""
        query listDiscounts($first: Int!, $after: String) {{
            discountNodes(first: $first, after: $after) {{
                edges {{
                    node {{
                        id
                        discount {{
                            {_DISCOUNT_FIELDS}
                        }}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """

    client = get_client()
    variables: dict = {"first": min(limit, 250)}
    nodes = client.graphql_paginated(
        gql, variables=variables, connection_path=["discountNodes"], max_results=limit,
    )
    discounts = [Discount.from_shopify(n).summary() for n in nodes]
    output_result(
        discounts, format=format, json_fields=json_fields,
        columns=["id", "title", "status", "code", "discount_type", "value"],
    )


@discount_app.command("view")
def view_discount(
    id: str = typer.Argument(..., help="Discount node ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed discount information."""
    client = get_client()
    gid = ShopifyClient.to_gid("DiscountNode", id)
    gql = f"""
        query getDiscount($id: ID!) {{
            discountNode(id: $id) {{
                id
                discount {{
                    {_DISCOUNT_FIELDS}
                }}
            }}
        }}
    """

    data = client.graphql(gql, variables={"id": gid})
    node = data.get("discountNode")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"Discount '{id}' not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    discount = Discount.from_shopify(node)
    output_result(discount.detail(), format=format, json_fields=json_fields)


@discount_app.command("create")
def create_discount(
    title: str = typer.Option(..., "--title", "-t", help="Discount title."),
    discount_type: str = typer.Option(
        ..., "--type", help="Discount type: percentage or fixed_amount."
    ),
    value: float = typer.Option(..., "--value", "-v", help="Discount value (percentage number or fixed amount)."),
    code: str | None = typer.Option(None, "--code", "-c", help="Discount code. Auto-generated if omitted."),
    starts_at: str | None = typer.Option(None, "--starts-at", help="Start date (ISO 8601)."),
    ends_at: str | None = typer.Option(None, "--ends-at", help="End date (ISO 8601)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a code-based discount."""
    # Build the value input based on type
    if discount_type == "percentage":
        value_input = {"percentage": value / 100.0}
    elif discount_type == "fixed_amount":
        value_input = {"discountAmount": {"amount": str(value), "appliesOnEachItem": False}}
    else:
        output_result(
            {"error": "INVALID_TYPE", "message": f"Invalid discount type: {discount_type}. Use 'percentage' or 'fixed_amount'."},
            format=format,
        )
        raise typer.Exit(code=1)

    discount_code = code if code else title.upper().replace(" ", "-")

    # startsAt is required in 2026-01 API — default to now
    from datetime import datetime, timezone
    effective_starts_at = starts_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    basic_code_discount: dict = {
        "title": title,
        "code": discount_code,
        "startsAt": effective_starts_at,
        "customerGets": {
            "value": value_input,
            "items": {"all": True},
        },
        "customerSelection": {"all": True},
        "combinesWith": {
            "orderDiscounts": False,
            "productDiscounts": False,
            "shippingDiscounts": False,
        },
    }
    if ends_at:
        basic_code_discount["endsAt"] = ends_at

    gql = """
        mutation discountCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
            discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
                codeDiscountNode {
                    id
                    codeDiscount {
                        ... on DiscountCodeBasic {
                            title
                            status
                            startsAt
                            endsAt
                            codes(first: 1) { edges { node { code } } }
                            customerGets {
                                value {
                                    ... on DiscountPercentage { percentage }
                                    ... on DiscountAmount { amount { amount currencyCode } }
                                }
                                items { ... on AllDiscountItems { allItems } }
                            }
                        }
                    }
                }
                userErrors { field message }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"basicCodeDiscount": basic_code_discount})
    code_node = data.get("discountCodeBasicCreate", {}).get("codeDiscountNode")
    if not code_node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Discount creation returned no discount."},
            format=format,
        )
        raise typer.Exit(code=1)

    # Reshape to match discountNode structure
    node = {
        "id": code_node.get("id", ""),
        "discount": code_node.get("codeDiscount", {}),
    }
    discount = Discount.from_shopify(node)
    output_result(discount.detail(), format=format, json_fields=json_fields)


@discount_app.command("delete")
def delete_discount(
    id: str = typer.Argument(..., help="Discount code node ID (numeric or GID)."),
) -> None:
    """Delete a code-based discount."""
    client = get_client()
    gid = ShopifyClient.to_gid("DiscountCodeNode", id)
    gql = """
        mutation discountDelete($id: ID!) {
            discountCodeDelete(id: $id) {
                deletedCodeDiscountId
                userErrors { field message }
            }
        }
    """
    data = client.graphql(gql, variables={"id": gid})
    deleted_id = data.get("discountCodeDelete", {}).get("deletedCodeDiscountId", "")
    output_result({"deleted": True, "id": deleted_id})

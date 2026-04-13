"""Gift card commands — gift card management.

Examples:
    ebshop gift-card list
    ebshop gift-card list --limit 10
    ebshop gift-card view gid://shopify/GiftCard/123
    ebshop gift-card create --initial-value 50.00
    ebshop gift-card create --initial-value 25.00 --note "Birthday gift" --customer-id 456
    ebshop gift-card disable gid://shopify/GiftCard/123
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.gift_card import GiftCard
from ebshop.output import Format, output_result

gift_card_app = typer.Typer(help="Gift card management.")


_GIFT_CARD_FIELDS = """
    id
    balance { amount currencyCode }
    initialValue { amount currencyCode }
    lastCharacters
    note
    enabled
    createdAt
    expiresOn
    customer { id }
"""


@gift_card_app.command("list")
def list_gift_cards(
    limit: int = typer.Option(50, "--limit", "-n", help="Max gift cards to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List gift cards."""
    gql = f"""
        query listGiftCards($first: Int!, $after: String) {{
            giftCards(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_GIFT_CARD_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """
    client = get_client()
    variables: dict = {"first": min(limit, 250)}
    nodes = client.graphql_paginated(
        gql, variables=variables, connection_path=["giftCards"], max_results=limit,
    )
    cards = [GiftCard.from_shopify(n).summary() for n in nodes]
    output_result(
        cards, format=format, json_fields=json_fields,
        columns=["id", "balance", "currency", "last_characters", "enabled"],
    )


@gift_card_app.command("view")
def view_gift_card(
    id: str = typer.Argument(..., help="Gift card ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed gift card information."""
    client = get_client()
    gid = ShopifyClient.to_gid("GiftCard", id)
    gql = f"""
        query getGiftCard($id: ID!) {{
            giftCard(id: $id) {{
                {_GIFT_CARD_FIELDS}
            }}
        }}
    """
    data = client.graphql(gql, variables={"id": gid})
    node = data.get("giftCard")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"Gift card '{id}' not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    card = GiftCard.from_shopify(node)
    output_result(card.detail(), format=format, json_fields=json_fields)


@gift_card_app.command("create")
def create_gift_card(
    initial_value: float = typer.Option(..., "--initial-value", help="Initial gift card value."),
    note: str | None = typer.Option(None, "--note", help="Note for the gift card."),
    customer_id: str | None = typer.Option(None, "--customer-id", help="Customer ID to associate."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a new gift card."""
    gift_card_input: dict = {
        "initialValue": str(initial_value),
    }
    if note:
        gift_card_input["note"] = note
    if customer_id:
        gift_card_input["customerId"] = ShopifyClient.to_gid("Customer", customer_id)

    gql = f"""
        mutation giftCardCreate($input: GiftCardCreateInput!) {{
            giftCardCreate(input: $input) {{
                giftCard {{
                    {_GIFT_CARD_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """
    client = get_client()
    data = client.graphql(gql, variables={"input": gift_card_input})
    card_node = data.get("giftCardCreate", {}).get("giftCard")
    if not card_node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Gift card creation returned no gift card."},
            format=format,
        )
        raise typer.Exit(code=1)

    card = GiftCard.from_shopify(card_node)
    output_result(card.detail(), format=format, json_fields=json_fields)


@gift_card_app.command("disable")
def disable_gift_card(
    id: str = typer.Argument(..., help="Gift card ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Disable a gift card."""
    client = get_client()
    gid = ShopifyClient.to_gid("GiftCard", id)
    gql = f"""
        mutation giftCardDisable($id: ID!) {{
            giftCardDisable(id: $id) {{
                giftCard {{
                    {_GIFT_CARD_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """
    data = client.graphql(gql, variables={"id": gid})
    card_node = data.get("giftCardDisable", {}).get("giftCard")
    if not card_node:
        output_result(
            {"error": "DISABLE_FAILED", "message": f"Failed to disable gift card '{id}'."},
            format=format,
        )
        raise typer.Exit(code=1)

    card = GiftCard.from_shopify(card_node)
    output_result(card.detail(), format=format, json_fields=json_fields)

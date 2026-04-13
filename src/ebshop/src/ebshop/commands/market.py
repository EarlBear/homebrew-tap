"""Market commands — international market management.

Examples:
    ebshop market list
    ebshop market list --limit 10
    ebshop market view gid://shopify/Market/123
    ebshop market create --name "North America" --countries "US,CA"
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.market import Market
from ebshop.output import Format, output_result

market_app = typer.Typer(help="International market management.")


_MARKET_FIELDS = """
    id
    name
    enabled
    primary
    currencySettings { baseCurrency { currencyCode } }
    regions(first: 50) {
        edges {
            node {
                name
                ... on MarketRegionCountry { code }
            }
        }
    }
"""


@market_app.command("list")
def list_markets(
    limit: int = typer.Option(50, "--limit", "-n", help="Max markets to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List all markets configured for the store."""
    gql = f"""
        query listMarkets($first: Int!, $after: String) {{
            markets(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_MARKET_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """
    client = get_client()
    variables: dict = {"first": min(limit, 250)}
    nodes = client.graphql_paginated(
        gql, variables=variables, connection_path=["markets"], max_results=limit,
    )
    markets = [Market.from_shopify(n).summary() for n in nodes]
    output_result(
        markets, format=format, json_fields=json_fields,
        columns=["id", "name", "enabled", "primary", "region_count"],
    )


@market_app.command("view")
def view_market(
    id: str = typer.Argument(..., help="Market ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed market information."""
    client = get_client()
    gid = ShopifyClient.to_gid("Market", id)
    gql = f"""
        query getMarket($id: ID!) {{
            market(id: $id) {{
                {_MARKET_FIELDS}
            }}
        }}
    """
    data = client.graphql(gql, variables={"id": gid})
    node = data.get("market")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"Market '{id}' not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    market = Market.from_shopify(node)
    output_result(market.detail(), format=format, json_fields=json_fields)


@market_app.command("create")
def create_market(
    name: str = typer.Option(..., "--name", help="Market name."),
    countries: str = typer.Option(..., "--countries", help="Comma-separated country codes (e.g. US,CA,GB)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a new market with specified countries."""
    country_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    regions = [{"countryCode": code} for code in country_list]

    gql = f"""
        mutation marketCreate($input: MarketCreateInput!) {{
            marketCreate(input: $input) {{
                market {{
                    {_MARKET_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """
    client = get_client()
    data = client.graphql(gql, variables={
        "input": {
            "name": name,
            "regions": regions,
        }
    })
    market_node = data.get("marketCreate", {}).get("market")
    if not market_node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Market creation returned no market."},
            format=format,
        )
        raise typer.Exit(code=1)

    market = Market.from_shopify(market_node)
    output_result(market.detail(), format=format, json_fields=json_fields)

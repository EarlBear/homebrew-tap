"""Shipping commands — zones, rates.

Examples:
    ebshop shipping zones
    ebshop shipping zones --limit 5
    ebshop shipping rates --zone-id gid://shopify/DeliveryProfileLocationGroup/1
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.shipping import ShippingRate, ShippingZone
from ebshop.output import Format, output_result

shipping_app = typer.Typer(help="Shipping rates and zones (read-only).")

# ── GraphQL fragments ──

ZONES_QUERY = """
    query DeliveryProfiles($first: Int!, $after: String) {
        deliveryProfiles(first: $first, after: $after) {
            edges {
                node {
                    id
                    name
                    profileLocationGroups {
                        locationGroup {
                            id
                        }
                        locationGroupZones(first: 20) {
                            edges {
                                node {
                                    zone {
                                        id
                                        name
                                        countries { name code }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            pageInfo { hasNextPage endCursor }
        }
    }
"""

RATES_QUERY = """
    query DeliveryProfilesForRates($first: Int!) {
        deliveryProfiles(first: $first) {
            edges {
                node {
                    id
                    name
                    profileLocationGroups {
                        locationGroup {
                            id
                        }
                        locationGroupZones(first: 20) {
                            edges {
                                node {
                                    zone { id name }
                                    methodDefinitions(first: 20) {
                                        edges {
                                            node {
                                                id
                                                name
                                                rateProvider {
                                                    ... on DeliveryRateDefinition {
                                                        id
                                                        price { amount currencyCode }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""


@shipping_app.command()
def zones(
    limit: int = typer.Option(10, "--limit", "-l", help="Max delivery profiles to fetch."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List shipping zones across all delivery profiles."""
    client = get_client()
    nodes = client.graphql_paginated(
        ZONES_QUERY,
        variables={"first": min(limit, 50)},
        connection_path=["deliveryProfiles"],
        max_results=limit,
    )

    zones_list: list[dict] = []
    for profile in nodes:
        profile_id = profile.get("id", "")
        profile_name = profile.get("name", "")
        for plg in profile.get("profileLocationGroups", []):
            zone_edges = plg.get("locationGroupZones", {}).get("edges", [])
            for edge in zone_edges:
                zone_node = edge.get("node", {}).get("zone", {})
                countries = [c.get("name", "") for c in zone_node.get("countries", [])]
                sz = ShippingZone(
                    id=zone_node.get("id", ""),
                    profile_id=profile_id,
                    profile_name=profile_name,
                    zone_name=zone_node.get("name", ""),
                    countries=countries,
                )
                zones_list.append(sz.summary())

    output_result(
        zones_list, format=format, json_fields=json_fields,
        columns=["id", "profile_name", "zone_name", "countries"],
    )


@shipping_app.command()
def rates(
    zone_id: str = typer.Option(..., "--zone-id", "-z", help="Zone GID to list rates for."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List shipping rates for a specific zone."""
    client = get_client()
    data = client.graphql(RATES_QUERY, variables={"first": 20})

    profile_edges = data.get("deliveryProfiles", {}).get("edges", [])
    rates_list: list[dict] = []

    for p_edge in profile_edges:
        profile = p_edge.get("node", {})
        for plg in profile.get("profileLocationGroups", []):
            zone_edges = plg.get("locationGroupZones", {}).get("edges", [])
            for z_edge in zone_edges:
                z_node = z_edge.get("node", {})
                zone = z_node.get("zone", {})
                if zone.get("id") != zone_id:
                    continue
                method_edges = z_node.get("methodDefinitions", {}).get("edges", [])
                for m_edge in method_edges:
                    method = m_edge.get("node", {})
                    provider = method.get("rateProvider", {})
                    price = provider.get("price", {})
                    sr = ShippingRate(
                        id=method.get("id", ""),
                        name=method.get("name", ""),
                        price_amount=price.get("amount", ""),
                        price_currency=price.get("currencyCode", ""),
                    )
                    rates_list.append(sr.summary())

    output_result(
        rates_list, format=format, json_fields=json_fields,
        columns=["id", "name", "price"],
    )

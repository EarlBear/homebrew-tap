"""Checkout branding commands — view and update checkout appearance.

Examples:
    ebshop checkout-branding view
    ebshop checkout-branding update --from-manifest
    ebshop checkout-branding update --primary-color "#8B4513"
    ebshop checkout-branding update --primary-color "#8B4513" --logo-url "https://..." --font "Roboto"
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from ebshop.client import get_client
from ebshop.output import Format, output_result


def _load_brand_colors() -> dict[str, str]:
    """Load brand colors from manifest.yaml."""
    try:
        import yaml
    except ImportError:
        return {}

    # Try common manifest locations
    candidates = [
        Path(os.environ.get("MANIFEST_FILE", "")),
        Path.cwd() / "shopify-cli" / "assets" / "manifest.yaml",
        Path.cwd() / "assets" / "manifest.yaml",
        Path(__file__).resolve().parents[3] / "assets" / "manifest.yaml",
    ]
    for p in candidates:
        if p.is_file():
            with open(p) as f:
                manifest = yaml.safe_load(f)
            return manifest.get("brand_identity", {}).get("colors", {})
    return {}

checkout_branding_app = typer.Typer(help="Checkout appearance customization.")


def _get_default_profile_id() -> str:
    """Fetch the default checkout profile ID."""
    client = get_client()
    data = client.graphql("""
        query {
            checkoutProfiles(first: 1) {
                edges {
                    node {
                        id
                        name
                        isPublished
                    }
                }
            }
        }
    """)
    edges = data.get("checkoutProfiles", {}).get("edges", [])
    if not edges:
        return ""
    return edges[0]["node"]["id"]


@checkout_branding_app.command("view")
def view_branding(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View current checkout branding settings."""
    profile_id = _get_default_profile_id()
    if not profile_id:
        output_result(
            {"error": "NO_PROFILE", "message": "No checkout profile found."},
            format=format,
        )
        raise typer.Exit(code=1)

    gql = """
        query getCheckoutBranding($checkoutProfileId: ID!) {
            checkoutBranding(checkoutProfileId: $checkoutProfileId) {
                customizations {
                    global {
                        cornerRadius
                    }
                }
                designSystem {
                    colors {
                        global {
                            accent
                            brand
                        }
                        schemes {
                            scheme1 {
                                base { accent background text }
                            }
                            scheme2 {
                                base { accent background text }
                            }
                        }
                    }
                    cornerRadius { base }
                    typography {
                        primary { name }
                        secondary { name }
                    }
                }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"checkoutProfileId": profile_id})
    branding = data.get("checkoutBranding") or {}

    result = {
        "profile_id": profile_id,
        "branding": branding,
    }
    output_result(result, format=format, json_fields=json_fields)


@checkout_branding_app.command("update")
def update_branding(
    from_manifest: bool = typer.Option(False, "--from-manifest", "-m", help="Read colors from manifest.yaml brand_identity."),
    primary_color: str | None = typer.Option(None, "--primary-color", "-c", help="Primary brand color hex (e.g. #8B4513)."),
    accent_color: str | None = typer.Option(None, "--accent-color", help="Accent color hex."),
    background_color: str | None = typer.Option(None, "--background-color", help="Background color hex."),
    text_color: str | None = typer.Option(None, "--text-color", help="Text color hex."),
    logo_url: str | None = typer.Option(None, "--logo-url", "-l", help="URL of the logo image."),
    font: str | None = typer.Option(None, "--font", help="Primary font family name."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Update checkout branding (colors, logo, font).

    Use --from-manifest to read brand colors from manifest.yaml automatically.
    CLI flags override manifest values when both are provided.

    Examples:
        ebshop checkout-branding update --from-manifest
        ebshop checkout-branding update --primary-color "#5C3D2E"
        ebshop checkout-branding update --from-manifest --font "Lato"
    """
    profile_id = _get_default_profile_id()
    if not profile_id:
        output_result(
            {"error": "NO_PROFILE", "message": "No checkout profile found."},
            format=format,
        )
        raise typer.Exit(code=1)

    # Load manifest colors as base, then overlay CLI flags
    if from_manifest:
        brand_colors = _load_brand_colors()
        if not brand_colors:
            output_result(
                {"error": "MANIFEST_NOT_FOUND", "message": "Could not load brand_identity.colors from manifest.yaml. Set MANIFEST_FILE env var or run from repo root."},
                format=format,
            )
            raise typer.Exit(code=1)
        primary_color = primary_color or brand_colors.get("primary")
        accent_color = accent_color or brand_colors.get("accent")
        background_color = background_color or brand_colors.get("background")
        text_color = text_color or brand_colors.get("text")

    if not primary_color:
        output_result(
            {"error": "MISSING_COLOR", "message": "Provide --primary-color or use --from-manifest."},
            format=format,
        )
        raise typer.Exit(code=1)

    # Build the branding input using 2026-01 schema
    colors: dict = {
        "global": {
            "brand": primary_color,
            "accent": accent_color or primary_color,
        },
        "schemes": {
            "scheme1": {
                "base": {
                    "accent": accent_color or primary_color,
                    "background": background_color or "#FFFFFF",
                    "text": text_color or "#2C2C2C",
                },
            },
        },
    }
    design_system: dict = {"colors": colors}

    if font:
        design_system["typography"] = {
            "primary": {"name": font},
        }

    customizations: dict = {}
    if logo_url:
        customizations["header"] = {
            "logo": {
                "image": {"mediaImageId": logo_url},
            },
        }

    gql = """
        mutation checkoutBrandingUpsert(
            $checkoutProfileId: ID!,
            $checkoutBrandingInput: CheckoutBrandingInput!
        ) {
            checkoutBrandingUpsert(
                checkoutProfileId: $checkoutProfileId,
                checkoutBrandingInput: $checkoutBrandingInput
            ) {
                checkoutBranding {
                    designSystem {
                        colors {
                            global { accent brand }
                            schemes {
                                scheme1 { base { accent background text } }
                            }
                        }
                        typography {
                            primary { name }
                        }
                    }
                }
                userErrors { field message }
            }
        }
    """

    branding_input: dict = {"designSystem": design_system}
    if customizations:
        branding_input["customizations"] = customizations

    client = get_client()
    data = client.graphql(gql, variables={
        "checkoutProfileId": profile_id,
        "checkoutBrandingInput": branding_input,
    })

    errors = data.get("checkoutBrandingUpsert", {}).get("userErrors", [])
    if errors:
        output_result(
            {"error": "BRANDING_FAILED", "errors": [e.get("message", "") for e in errors]},
            format=format,
        )
        raise typer.Exit(code=1)

    branding = data.get("checkoutBrandingUpsert", {}).get("checkoutBranding")
    result = {
        "updated": True,
        "profile_id": profile_id,
        "source": "manifest" if from_manifest else "cli_flags",
        "colors_applied": {
            "primary": primary_color,
            "accent": accent_color,
            "background": background_color,
            "text": text_color,
        },
        "branding": branding or {},
    }
    output_result(result, format=format, json_fields=json_fields)

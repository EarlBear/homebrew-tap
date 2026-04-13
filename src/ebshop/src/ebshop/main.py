"""EarlBear Shopify CLI — agent-first Shopify Admin API interface.

Usage:
    ebshop --help              Show all command groups
    ebshop <group> --help      Show commands in a group
    ebshop <group> <cmd> -h    Show command options and examples
    ebshop --help-json         Dump full command tree as JSON (for agents)
    ebshop --version           Show version
"""

from __future__ import annotations

import json

import typer

from ebshop import __version__
from ebshop.client import ShopifyError
from ebshop.output import output_error

app = typer.Typer(
    name="ebshop",
    help="Shopify CLI for agents and humans.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        print(json.dumps({"name": "ebshop", "version": __version__}))
        raise typer.Exit()


def help_json_callback(value: bool) -> None:
    """Dump the full command tree as JSON for programmatic discovery."""
    if value:
        tree = _build_command_tree(app)
        print(json.dumps(tree, indent=2))
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version.",
    ),
    help_json: bool | None = typer.Option(
        None, "--help-json", callback=help_json_callback, is_eager=True,
        help="Dump full command tree as JSON (for agent introspection).",
        hidden=True,
    ),
) -> None:
    """EarlBear Shopify CLI — agent-first Shopify Admin API interface."""
    pass


def _build_command_tree(typer_app: typer.Typer) -> dict:
    """Build a JSON-serializable command tree from a Typer app."""
    click_app = typer.main.get_command(typer_app)
    return _click_to_dict(click_app)


def _click_to_dict(cmd) -> dict:  # noqa: ANN001
    """Recursively convert a Click command/group to a dict."""
    import click

    result: dict = {
        "name": cmd.name or "",
        "description": (cmd.help or "").strip().split("\n")[0],
    }

    if isinstance(cmd, click.Group):
        commands = {}
        for name in cmd.list_commands(click.Context(cmd)):
            sub = cmd.get_command(click.Context(cmd), name)
            if sub and not sub.hidden:
                commands[name] = _click_to_dict(sub)
        if commands:
            result["commands"] = commands
    else:
        params = []
        for param in cmd.params:
            if isinstance(param, click.Option):
                if param.hidden or param.name == "help":
                    continue
                p: dict = {
                    "name": param.opts[0] if param.opts else param.name,
                    "type": param.type.name if hasattr(param.type, "name") else str(param.type),
                    "required": param.required,
                }
                if param.default is not None:
                    p["default"] = param.default
                if param.help:
                    p["help"] = param.help
                params.append(p)
            elif isinstance(param, click.Argument):
                params.append({
                    "name": param.name,
                    "type": param.type.name if hasattr(param.type, "name") else str(param.type),
                    "required": param.required,
                })
        if params:
            result["options"] = params

    return result


# ── discover command ──
from ebshop._discover import discover_command
app.command("discover")(discover_command)


# ── Register command groups ──

def _register_commands() -> None:
    """Import and register all command group sub-apps."""
    from ebshop.commands.auth import auth_app
    from ebshop.commands.analytics import analytics_app
    from ebshop.commands.blog import blog_app
    from ebshop.commands.checkout_branding import checkout_branding_app
    from ebshop.commands.collection import collection_app
    from ebshop.commands.customer import customer_app
    from ebshop.commands.discount import discount_app
    from ebshop.commands.draft_order import draft_order_app
    from ebshop.commands.file import file_app
    from ebshop.commands.fulfillment_order import fulfillment_order_app
    from ebshop.commands.gift_card import gift_card_app
    from ebshop.commands.inventory import inventory_app
    from ebshop.commands.locale import locale_app
    from ebshop.commands.market import market_app
    from ebshop.commands.metafield import metafield_app
    from ebshop.commands.navigation import navigation_app
    from ebshop.commands.order import order_app
    from ebshop.commands.page import page_app
    from ebshop.commands.product import product_app
    from ebshop.commands.return_ import return_app
    from ebshop.commands.script_tag import script_tag_app
    from ebshop.commands.shipping import shipping_app
    from ebshop.commands.shop import shop_app
    from ebshop.commands.theme import theme_app
    from ebshop.commands.translation import translation_app
    from ebshop.commands.webhook import webhook_app

    app.add_typer(auth_app, name="auth", help="Authentication — login and credential status")
    app.add_typer(analytics_app, name="analytics", help="Sales analytics computed from order data")
    app.add_typer(blog_app, name="blog", help="Blog management — list, view, articles, create-article")
    app.add_typer(checkout_branding_app, name="checkout-branding", help="Checkout appearance customization")
    app.add_typer(collection_app, name="collection", help="Collection management — list, view, create, update, products, add/remove-products")
    app.add_typer(customer_app, name="customer", help="Customer management — list, view, search, create, update, orders, tags")
    app.add_typer(discount_app, name="discount", help="Discount management — list, view, create, delete")
    app.add_typer(draft_order_app, name="draft-order", help="Draft order management — list, view, create, complete, delete")
    app.add_typer(file_app, name="file", help="File and asset management — list, view, upload, delete")
    app.add_typer(fulfillment_order_app, name="fulfillment-order", help="Fulfillment order workflow — list, accept, reject")
    app.add_typer(gift_card_app, name="gift-card", help="Gift card management — list, view, create, disable")
    app.add_typer(shop_app, name="shop", help="Store info and health check")
    app.add_typer(product_app, name="product", help="Product management — list, view, create, update, delete, variants, images")
    app.add_typer(locale_app, name="locale", help="Store language management — list, enable, disable")
    app.add_typer(market_app, name="market", help="International market management — list, view, create")
    app.add_typer(navigation_app, name="navigation", help="Online Store navigation/menu management")
    app.add_typer(order_app, name="order", help="Order management — list, view, fulfill, cancel, notes")
    app.add_typer(inventory_app, name="inventory", help="Inventory levels, locations, and adjustments")
    app.add_typer(page_app, name="page", help="Online Store page management — list, view, create, update, delete")
    app.add_typer(return_app, name="return", help="Return management — list, view, create")
    app.add_typer(script_tag_app, name="script-tag", help="Storefront JavaScript injection")
    app.add_typer(shipping_app, name="shipping", help="Shipping rates and zones")
    app.add_typer(theme_app, name="theme", help="Theme management — list, view, assets, get-asset, update-asset, publish")
    app.add_typer(translation_app, name="translation", help="Content translation management — list, set, delete")
    app.add_typer(webhook_app, name="webhook", help="Webhook subscription management")
    app.add_typer(metafield_app, name="metafield", help="Metafield management — list, get, set, delete")


_register_commands()


def main() -> None:
    """CLI entry point."""
    import sys
    import time as _time

    from ebshop.logging import is_enabled, log_command

    args = sys.argv[1:]
    cmd_str = " ".join(args[:3]) if args else "help"

    start = _time.monotonic()
    exit_code = 0
    error_msg = None

    try:
        app()
    except ShopifyError as e:
        exit_code = 1
        error_msg = e.message
        output_error(
            error=f"SHOPIFY_{e.status_code}",
            message=e.message,
            status=1,
        )
    except KeyboardInterrupt:
        exit_code = 130
        raise SystemExit(130)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        raise
    finally:
        if is_enabled():
            duration_ms = int((_time.monotonic() - start) * 1000)
            log_command(
                command=cmd_str,
                args=" ".join(args),
                exit_code=exit_code,
                duration_ms=duration_ms,
                error_message=error_msg,
            )

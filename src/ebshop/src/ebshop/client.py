"""Shopify GraphQL Admin API client using httpx.

Primary interface is graphql() for queries/mutations and graphql_paginated()
for cursor-based connection traversal. REST fallback methods are available
for endpoints not yet in GraphQL.

All methods return raw dicts — Pydantic parsing happens at the command layer.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

from ebshop.config import get_config


class ShopifyError(Exception):
    """Raised when the Shopify API returns an error."""

    def __init__(self, status_code: int, message: str, errors: list | None = None):
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        super().__init__(f"[{status_code}] {message}")


class ShopifyClient:
    """HTTP client for the Shopify Admin API (GraphQL + REST)."""

    def __init__(self) -> None:
        config = get_config()
        missing = config.validate()
        if missing:
            print(
                f'{{"error": "CONFIG_MISSING", "message": "Missing required config: {", ".join(missing)}"}}',
                file=sys.stderr,
            )
            sys.exit(2)

        self.store_url = config.store_url.rstrip("/")
        self.api_version = config.api_version
        self._client = httpx.Client(
            headers={
                "X-Shopify-Access-Token": config.access_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._available_points: float = 1000.0
        self._restore_rate: float = 50.0

    def close(self) -> None:
        self._client.close()

    # ── GraphQL ──

    @property
    def graphql_url(self) -> str:
        return f"{self.store_url}/admin/api/{self.api_version}/graphql.json"

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query/mutation. Returns the 'data' dict.

        Raises ShopifyError on GraphQL user errors or HTTP failures.
        Tracks rate limit budget from extensions.cost.throttleStatus.
        """
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        resp = self._client.post(self.graphql_url, json=body)

        if not resp.is_success:
            raise ShopifyError(resp.status_code, resp.text)

        result = resp.json()

        # Track rate limit from extensions
        extensions = result.get("extensions", {})
        cost = extensions.get("cost", {})
        throttle = cost.get("throttleStatus", {})
        if throttle:
            self._available_points = throttle.get("currentlyAvailable", 1000.0)
            self._restore_rate = throttle.get("restoreRate", 50.0)

        # GraphQL errors are in the response body, not HTTP status
        if "errors" in result and result["errors"]:
            messages = [e.get("message", "") for e in result["errors"]]
            raise ShopifyError(200, "; ".join(messages), result["errors"])

        # userErrors inside mutations
        data = result.get("data", {})
        if data:
            for key, value in data.items():
                if isinstance(value, dict) and "userErrors" in value:
                    user_errors = value["userErrors"]
                    if user_errors:
                        messages = [e.get("message", "") for e in user_errors]
                        raise ShopifyError(422, "; ".join(messages))

        return data

    def graphql_paginated(
        self,
        query: str,
        variables: dict | None = None,
        connection_path: list[str] | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Auto-paginate a GraphQL connection using cursor-based pagination.

        Args:
            query: GraphQL query with $first and $after variables.
            variables: Query variables (must include 'first', may include 'after').
            connection_path: Path to the connection in the response data,
                e.g. ["products"] to reach data.products.edges.
            max_results: Maximum total results to fetch.

        Returns:
            List of node dicts from the connection edges.
        """
        variables = dict(variables or {})
        connection_path = connection_path or []
        all_nodes: list[dict] = []
        cursor: str | None = None

        while True:
            if cursor:
                variables["after"] = cursor
            elif "after" in variables:
                del variables["after"]

            data = self.graphql(query, variables)

            # Navigate to the connection
            connection = data
            for key in connection_path:
                connection = connection.get(key, {})

            edges = connection.get("edges", [])
            for edge in edges:
                all_nodes.append(edge["node"])

            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage") or len(all_nodes) >= max_results:
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

        return all_nodes[:max_results]

    # ── REST fallback ──

    def _rest_url(self, path: str) -> str:
        """Build a REST Admin API URL."""
        return f"{self.store_url}/admin/api/{self.api_version}{path}"

    def _handle_rest_response(self, resp: httpx.Response) -> Any:
        """Parse REST response, raise ShopifyError on non-2xx."""
        if resp.status_code == 204:
            return None
        if resp.is_success:
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.content
        try:
            body = resp.json()
            message = body.get("errors", resp.text)
            if isinstance(message, dict):
                parts = [f"{k}: {v}" for k, v in message.items()]
                message = "; ".join(parts)
            elif isinstance(message, list):
                message = "; ".join(str(e) for e in message)
        except Exception:
            message = resp.text or f"HTTP {resp.status_code}"
        raise ShopifyError(resp.status_code, str(message))

    def rest_get(self, path: str, params: dict | None = None) -> Any:
        resp = self._client.get(self._rest_url(path), params=params)
        return self._handle_rest_response(resp)

    def rest_post(self, path: str, json: Any = None) -> Any:
        resp = self._client.post(self._rest_url(path), json=json)
        return self._handle_rest_response(resp)

    def rest_put(self, path: str, json: Any = None) -> Any:
        resp = self._client.put(self._rest_url(path), json=json)
        return self._handle_rest_response(resp)

    def rest_delete(self, path: str) -> Any:
        resp = self._client.delete(self._rest_url(path))
        return self._handle_rest_response(resp)

    # ── Helpers ──

    @staticmethod
    def to_gid(resource_type: str, id_or_gid: str) -> str:
        """Normalize an ID to a Shopify global ID.

        Accepts either a numeric ID or a full GID string.
        """
        id_str = str(id_or_gid)
        if id_str.startswith("gid://"):
            return id_str
        return f"gid://shopify/{resource_type}/{id_str}"

    @staticmethod
    def from_gid(gid: str) -> str:
        """Extract the numeric ID from a Shopify global ID."""
        if gid.startswith("gid://"):
            return gid.rsplit("/", 1)[-1]
        return gid


# Singleton
_client: ShopifyClient | None = None


def get_client() -> ShopifyClient:
    """Get the global client singleton."""
    global _client
    if _client is None:
        _client = ShopifyClient()
    return _client


def reset_client() -> None:
    """Reset the client singleton (for testing)."""
    global _client
    if _client is not None:
        _client.close()
    _client = None

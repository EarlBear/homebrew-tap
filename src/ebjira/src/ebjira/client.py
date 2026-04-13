"""Jira REST API client using httpx.

Supports both Platform v3 and Agile 1.0 APIs.
All methods return raw dicts — Pydantic parsing happens at the command layer.
"""

from __future__ import annotations

import base64
import sys
from typing import Any

import httpx

from ebjira.config import get_config


class JiraError(Exception):
    """Raised when the Jira API returns an error."""

    def __init__(self, status_code: int, message: str, errors: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.errors = errors or {}
        super().__init__(f"[{status_code}] {message}")


class JiraClient:
    """HTTP client for the Jira Cloud REST API."""

    def __init__(self) -> None:
        config = get_config()
        missing = config.validate()
        if missing:
            print(
                f'{{"error": "CONFIG_MISSING", "message": "Missing required config: {", ".join(missing)}"}}',
                file=sys.stderr,
            )
            sys.exit(2)

        self.base_url = config.base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=(config.user_email, config.api_token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    # ── Core HTTP methods ──

    def _handle_response(self, resp: httpx.Response) -> Any:
        """Parse response, raise JiraError on non-2xx."""
        if resp.status_code in (201, 204) and not resp.content.strip():
            return None
        if resp.is_success:
            if resp.headers.get("content-type", "").startswith("application/json") and resp.content.strip():
                return resp.json()
            if not resp.content.strip():
                return None
            return resp.content
        # Error path
        try:
            body = resp.json()
            message = body.get("errorMessages", [body.get("message", str(body))])
            if isinstance(message, list):
                message = "; ".join(message) if message else str(body)
            errors = body.get("errors", {})
        except Exception:
            message = resp.text or f"HTTP {resp.status_code}"
            errors = {}
        raise JiraError(resp.status_code, message, errors)

    def get(self, path: str, params: dict | None = None) -> Any:
        resp = self._client.get(path, params=params)
        return self._handle_response(resp)

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        resp = self._client.post(path, json=json, **kwargs)
        return self._handle_response(resp)

    def put(self, path: str, json: Any = None) -> Any:
        resp = self._client.put(path, json=json)
        return self._handle_response(resp)

    def delete(self, path: str, params: dict | None = None) -> Any:
        resp = self._client.delete(path, params=params)
        return self._handle_response(resp)

    # ── Pagination ──

    def get_paginated(
        self,
        path: str,
        results_key: str = "values",
        params: dict | None = None,
        max_results: int | None = None,
    ) -> list[dict]:
        """Fetch all pages from a paginated Jira endpoint.

        Works with both offset-based (startAt/maxResults) and token-based pagination.
        """
        params = dict(params or {})
        all_results: list[dict] = []
        start_at = 0
        page_size = min(max_results or 50, 50)

        while True:
            params["startAt"] = start_at
            params["maxResults"] = page_size
            data = self.get(path, params=params)

            if isinstance(data, dict):
                results = data.get(results_key, [])
                total = data.get("total", len(results))
            else:
                break

            all_results.extend(results)

            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            start_at += len(results)
            if start_at >= total or not results:
                break

        return all_results

    def get_agile_paginated(
        self,
        path: str,
        results_key: str = "values",
        params: dict | None = None,
        max_results: int | None = None,
    ) -> list[dict]:
        """Fetch all pages from an Agile API endpoint (uses isLast flag)."""
        params = dict(params or {})
        all_results: list[dict] = []
        start_at = 0
        page_size = min(max_results or 50, 50)

        while True:
            params["startAt"] = start_at
            params["maxResults"] = page_size
            data = self.get(path, params=params)

            if isinstance(data, dict):
                results = data.get(results_key, [])
            else:
                break

            all_results.extend(results)

            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            is_last = data.get("isLast", True)
            if is_last or not results:
                break

            start_at += len(results)

        return all_results

    # ── Search JQL (token-based pagination) ──

    def search_jql_all(
        self,
        jql: str,
        fields: list[str],
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch issues using /search/jql with token-based pagination.

        The enhanced search endpoint (/search/jql) uses nextPageToken, not
        startAt/total.  This method handles multi-page result sets
        transparently.
        """
        all_issues: list[dict] = []
        next_token: str | None = None

        while True:
            body: dict = {
                "jql": jql,
                "maxResults": min(max_results - len(all_issues), 50),
                "fields": fields,
            }
            if next_token:
                body["nextPageToken"] = next_token

            data = self.post(self.platform("/search/jql"), json=body)
            issues = data.get("issues", [])
            all_issues.extend(issues)

            if data.get("isLast", True) or len(all_issues) >= max_results:
                break

            next_token = data.get("nextPageToken")
            if not next_token:
                break

        return all_issues[:max_results]

    # ── Platform API v3 ──

    def platform(self, path: str) -> str:
        """Build a platform API v3 path."""
        return f"/rest/api/3{path}"

    # ── Agile API 1.0 ──

    def agile(self, path: str) -> str:
        """Build an agile API 1.0 path."""
        return f"/rest/agile/1.0{path}"

    # ── File upload (multipart) ──

    def upload_attachment(self, issue_key: str, filename: str, content: bytes) -> Any:
        """Upload a file attachment to an issue.

        Temporarily removes the default Content-Type header so httpx can
        set the correct multipart/form-data boundary automatically.
        """
        saved_ct = self._client.headers.get("content-type")
        del self._client.headers["content-type"]
        try:
            resp = self._client.post(
                self.platform(f"/issue/{issue_key}/attachments"),
                headers={"X-Atlassian-Token": "no-check"},
                files={"file": (filename, content)},
            )
            return self._handle_response(resp)
        finally:
            if saved_ct:
                self._client.headers["content-type"] = saved_ct

    def upload_attachment_base64(
        self, issue_key: str, filename: str, base64_content: str
    ) -> Any:
        """Upload a base64-encoded file attachment to an issue."""
        content = base64.b64decode(base64_content)
        return self.upload_attachment(issue_key, filename, content)


# Singleton
_client: JiraClient | None = None


def get_client() -> JiraClient:
    """Get the global client singleton."""
    global _client
    if _client is None:
        _client = JiraClient()
    return _client


def reset_client() -> None:
    """Reset the client singleton (for testing)."""
    global _client
    if _client is not None:
        _client.close()
    _client = None

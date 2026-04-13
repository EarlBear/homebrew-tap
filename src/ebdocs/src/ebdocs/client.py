"""Google Docs and Drive API client.

Wraps google-api-python-client with a singleton pattern.
All methods return raw dicts — Pydantic parsing happens at the command layer.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

# EBDOCS_DEBUG=1 enables verbose logging from httplib2, google-auth, urllib3
if os.environ.get("EBDOCS_DEBUG", "").lower() in ("1", "true"):
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    for name in ("httplib2", "google.auth", "google_auth_httplib2", "googleapiclient", "urllib3"):
        logging.getLogger(name).setLevel(logging.DEBUG)
from googleapiclient.errors import HttpError

from ebdocs.auth import load_credentials
from ebdocs.config import get_config


def _make_http():
    """Create an httplib2.Http with proxy and CA certs configured.

    google-api-python-client always uses httplib2 internally. In cloud
    environments (Anthropic cloud), DNS is unavailable — all traffic must
    go through the egress proxy.

    This function:
    1. Auto-sets HTTPLIB2_CA_CERTS if not set (proxy does TLS interception)
    2. Eagerly parses HTTPS_PROXY into a ProxyInfo with proxy_rdns=True
    3. Forces proxy via bypass_host=False (ignores NO_PROXY without clearing it)

    We do NOT clear NO_PROXY — httpx-based CLIs (ebjira, ebshop) work fine
    with it set. Instead, we override httplib2's bypass logic directly.
    """
    debug = os.environ.get("EBDOCS_DEBUG", "").lower() in ("1", "true")
    kwargs = {}

    if debug and (os.environ.get("NO_PROXY") or os.environ.get("no_proxy")):
        print(f"[ebdocs] NO_PROXY={os.environ.get('NO_PROXY', '')} (ignored — bypass_host overridden)", file=sys.stderr)

    # Set HTTPLIB2_CA_CERTS if not set — proxy does TLS interception with self-signed CA
    ca_certs = os.environ.get("HTTPLIB2_CA_CERTS")
    if not ca_certs and os.path.exists("/etc/ssl/certs/ca-certificates.crt"):
        ca_certs = "/etc/ssl/certs/ca-certificates.crt"
        os.environ["HTTPLIB2_CA_CERTS"] = ca_certs
        if debug:
            print(f"[ebdocs] Auto-set HTTPLIB2_CA_CERTS={ca_certs}", file=sys.stderr)
    if ca_certs:
        kwargs["ca_certs"] = ca_certs

    # Check PySocks availability — httplib2 silently ignores proxy without it
    try:
        import socks  # noqa: F401
        has_pysocks = True
    except ImportError:
        has_pysocks = False
        if debug:
            print("[ebdocs] WARNING: PySocks not installed — httplib2 proxy will be ignored", file=sys.stderr)

    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy_url and has_pysocks:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        proxy_info = httplib2.ProxyInfo(
            proxy_type=3,  # PROXY_TYPE_HTTP
            proxy_host=parsed.hostname,
            proxy_port=parsed.port or 8080,
            proxy_rdns=True,  # Proxy handles DNS — no local resolution
            proxy_user=parsed.username,
            proxy_pass=parsed.password,
        )
        # Force proxy even if NO_PROXY includes googleapis.com.
        proxy_info.bypass_host = lambda host: False
        kwargs["proxy_info"] = proxy_info
        if debug:
            print(f"[ebdocs] proxy: {parsed.hostname}:{parsed.port} rdns=True bypass=disabled", file=sys.stderr)
    elif proxy_url and not has_pysocks:
        print(f"[ebdocs] ERROR: HTTPS_PROXY={proxy_url} but PySocks missing — proxy WILL NOT WORK", file=sys.stderr)
    elif debug:
        print("[ebdocs] No HTTPS_PROXY set — direct connection", file=sys.stderr)

    if debug:
        print(f"[ebdocs] httplib2={httplib2.__file__}", file=sys.stderr)
        print(f"[ebdocs] ca_certs={ca_certs or 'default'}", file=sys.stderr)
        print(f"[ebdocs] NO_PROXY={os.environ.get('NO_PROXY', '<not set>')}", file=sys.stderr)

    return httplib2.Http(**kwargs)


class DocsError(Exception):
    """Raised when a Google API call fails."""

    def __init__(self, status_code: int, message: str, errors: list[dict] | None = None):
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        super().__init__(f"[{status_code}] {message}")


def _wrap_http_error(e: HttpError) -> DocsError:
    """Convert a googleapiclient HttpError to DocsError."""
    status = e.resp.status if e.resp else 500
    try:
        body = json.loads(e.content)
        error_info = body.get("error", {})
        message = error_info.get("message", str(e))
        errors = error_info.get("errors", [])
    except (json.JSONDecodeError, AttributeError):
        message = str(e)
        errors = []
    return DocsError(status_code=status, message=message, errors=errors)


def _debug(msg: str, *args: Any) -> None:
    """Print debug message if EBDOCS_DEBUG is set."""
    if os.environ.get("EBDOCS_DEBUG", "").lower() in ("1", "true"):
        print(f"[ebdocs] {msg % args}" if args else f"[ebdocs] {msg}", file=sys.stderr)


class DocsClient:
    """Client for Google Docs and Drive APIs.

    Supports automatic fallback to MCP Worker REST API when the proxy
    blocks direct Google API calls (403). Set MCP_OAUTH_CLIENT_ID and
    MCP_OAUTH_CLIENT_SECRET to enable the fallback.
    """

    def __init__(self) -> None:
        config = get_config()
        missing = config.validate()
        if missing:
            print(
                json.dumps({
                    "error": "CONFIG_MISSING",
                    "message": f"Missing required config: {', '.join(missing)}",
                }),
                file=sys.stderr,
            )
            sys.exit(2)

        creds = load_credentials()
        http = AuthorizedHttp(creds, http=_make_http())
        self._docs = build("docs", "v1", http=http, cache_discovery=False)
        self._drive = build("drive", "v3", http=http, cache_discovery=False)
        self._folder_id = config.drive_folder_id

        # MCP Worker REST API fallback
        self._mcp_api_url = os.environ.get(
            "GDOCS_MCP_API_URL",
            "https://gdocs-mcp.omar-aed.workers.dev/api",
        )
        self._mcp_auth = self._load_mcp_auth()
        if self._mcp_auth:
            _debug("MCP fallback available: %s", self._mcp_api_url)

    def _load_mcp_auth(self) -> tuple[str, str] | None:
        """Load MCP OAuth credentials for REST API fallback."""
        client_id = os.environ.get("MCP_OAUTH_CLIENT_ID")
        client_secret = os.environ.get("MCP_OAUTH_CLIENT_SECRET")
        if client_id and client_secret:
            return (client_id, client_secret)
        return None

    def _mcp_request(
        self,
        endpoint: str,
        method: str = "POST",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Call MCP Worker REST API as fallback when proxy blocks Google APIs."""
        if not self._mcp_auth:
            raise DocsError(403, "MCP fallback unavailable — MCP_OAUTH_CLIENT_ID/SECRET not set")

        import httpx

        url = f"{self._mcp_api_url}/{endpoint}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if qs:
                url += "?" + qs

        _debug("MCP fallback: %s %s", method, url)

        try:
            resp = httpx.request(
                method,
                url,
                auth=httpx.BasicAuth(*self._mcp_auth),
                json=json_body if method in ("POST", "PATCH") else None,
                timeout=30.0,
            )
            if resp.status_code != 200:
                raise DocsError(resp.status_code, f"MCP API error: {resp.text}")
            return resp.json()
        except httpx.HTTPError as e:
            raise DocsError(502, f"MCP API connection error: {e}")

    def close(self) -> None:
        """Close underlying HTTP connections."""
        self._docs.close()
        self._drive.close()

    # ── Document CRUD ──

    def create_document(self, title: str) -> dict:
        """Create a new Google Doc and move it to the shared folder.

        Returns the document resource dict.
        """
        try:
            doc = self._docs.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]
            if self._folder_id:
                self.move_to_folder(doc_id, self._folder_id)
            return doc
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/create", json_body={"title": title})
            raise _wrap_http_error(e)

    def get_document(self, document_id: str) -> dict:
        """Get full document resource including body content."""
        try:
            return self._docs.documents().get(documentId=document_id).execute()
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/read", method="GET", params={"document_id": document_id, "format": "text"})
            raise _wrap_http_error(e)

    def batch_update(self, document_id: str, requests: list[dict]) -> dict:
        """Apply a list of batchUpdate requests to a document.

        Args:
            document_id: The document ID.
            requests: List of request dicts per the Docs API batchUpdate spec.

        Returns:
            The batchUpdate response.
        """
        try:
            return (
                self._docs.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                # Extract text from insertText requests for simple writes
                text_parts = []
                for req in requests:
                    if "insertText" in req:
                        text_parts.append(req["insertText"].get("text", ""))
                if text_parts:
                    return self._mcp_request("docs/write", json_body={
                        "document_id": document_id,
                        "content": "".join(text_parts),
                    })
            raise _wrap_http_error(e)

    def write_markdown(self, document_id: str, markdown: str, replace: bool = True) -> dict:
        """Write markdown to a Google Doc with formatting via MCP Worker.

        The MCP Worker converts markdown to Google Docs formatting:
        headings, bold, italic, links, lists, tables, named ranges.

        Args:
            document_id: The document ID.
            markdown: Markdown content to write.
            replace: Replace existing content (True) or append (False).

        Returns:
            Status dict with document URL and block counts.
        """
        return self._mcp_request("docs/write-markdown", json_body={
            "document_id": document_id,
            "markdown": markdown,
            "replace": replace,
        })

    # ── Drive operations ──

    def move_to_folder(self, file_id: str, folder_id: str) -> dict:
        """Move a file to a specific Drive folder (supports Shared Drives)."""
        try:
            # Get current parents to remove
            file = self._drive.files().get(
                fileId=file_id, fields="parents",
                supportsAllDrives=True,
            ).execute()
            previous_parents = ",".join(file.get("parents", []))
            return (
                self._drive.files()
                .update(
                    fileId=file_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields="id, parents",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as e:
            raise _wrap_http_error(e)

    def share(
        self, file_id: str, email: str, role: str = "writer", send_notification: bool = False
    ) -> dict:
        """Share a file with a user by email.

        Args:
            file_id: The file ID.
            email: Email address to share with.
            role: Permission role (reader, commenter, writer, owner).
            send_notification: Whether to send an email notification.

        Returns:
            The permission resource dict.
        """
        try:
            return (
                self._drive.permissions()
                .create(
                    fileId=file_id,
                    body={"type": "user", "role": role, "emailAddress": email},
                    sendNotificationEmail=send_notification,
                    fields="id, emailAddress, role, type",
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/share", json_body={
                    "document_id": file_id, "email": email, "role": role,
                })
            raise _wrap_http_error(e)

    def list_permissions(self, file_id: str) -> list[dict]:
        """List all permissions on a file."""
        try:
            result = (
                self._drive.permissions()
                .list(
                    fileId=file_id,
                    fields="permissions(id, emailAddress, role, type, displayName)",
                )
                .execute()
            )
            return result.get("permissions", [])
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/share/list", method="GET", params={"document_id": file_id})
            raise _wrap_http_error(e)

    def remove_permission(self, file_id: str, permission_id: str) -> None:
        """Remove a permission from a file."""
        try:
            self._drive.permissions().delete(
                fileId=file_id, permissionId=permission_id
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                self._mcp_request("docs/share/remove", method="DELETE", params={
                    "document_id": file_id, "permission_id": permission_id,
                })
                return
            raise _wrap_http_error(e)

    # ── Folder operations ──

    FOLDER_MIME = "application/vnd.google-apps.folder"

    def list_folders(self, parent_id: str | None = None, max_results: int = 200) -> list[dict]:
        """List subfolders of a given folder.

        Returns list of folder dicts with id, name, parents, createdTime, modifiedTime.
        """
        parent = parent_id or self._folder_id
        query = f"'{parent}' in parents and trashed = false and mimeType = '{self.FOLDER_MIME}'"
        try:
            all_folders: list[dict] = []
            page_token: str | None = None
            while True:
                result = (
                    self._drive.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, parents, createdTime, modifiedTime)",
                        pageSize=min(max_results - len(all_folders), 100),
                        pageToken=page_token,
                        orderBy="name",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                all_folders.extend(result.get("files", []))
                page_token = result.get("nextPageToken")
                if not page_token or len(all_folders) >= max_results:
                    break
            return all_folders[:max_results]
        except HttpError as e:
            raise _wrap_http_error(e)

    def find_folder_by_name(self, name: str, parent_id: str | None = None) -> dict | None:
        """Find a folder by name under a parent (first match)."""
        parent = parent_id or self._folder_id
        # Escape single quotes in name for query
        safe_name = name.replace("'", "\\'")
        query = (
            f"'{parent}' in parents and trashed = false "
            f"and mimeType = '{self.FOLDER_MIME}' and name = '{safe_name}'"
        )
        try:
            result = (
                self._drive.files()
                .list(
                    q=query,
                    fields="files(id, name, parents, createdTime, modifiedTime)",
                    pageSize=10,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            files = result.get("files", [])
            return files[0] if files else None
        except HttpError as e:
            raise _wrap_http_error(e)

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        """Create a new Drive folder under a parent.

        Returns the created folder dict with id, name, parents.
        """
        parent = parent_id or self._folder_id
        body = {
            "name": name,
            "mimeType": self.FOLDER_MIME,
            "parents": [parent] if parent else [],
        }
        try:
            return (
                self._drive.files()
                .create(
                    body=body,
                    fields="id, name, parents, createdTime, modifiedTime, webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as e:
            raise _wrap_http_error(e)

    def ensure_folder(self, name: str, parent_id: str | None = None) -> dict:
        """Find or create a folder by name under a parent."""
        existing = self.find_folder_by_name(name, parent_id)
        if existing:
            return existing
        return self.create_folder(name, parent_id)

    def ensure_folder_path(self, path: str, root_id: str | None = None) -> dict:
        """Ensure a nested folder path exists under a root, creating as needed.

        Example: ensure_folder_path("knowledge-base/ecommerce-fundamentals", root)
        returns the leaf folder dict.
        """
        parent_id = root_id or self._folder_id
        current = {"id": parent_id}
        for segment in path.strip("/").split("/"):
            if not segment:
                continue
            current = self.ensure_folder(segment, current["id"])
        return current

    def walk_folder_tree(self, folder_id: str | None = None) -> list[tuple[str, dict]]:
        """BFS walk a Drive folder tree, yielding (relative_path, file_dict) for every Google Doc.

        Relative path is the folder path from the root (e.g. "subfolder/nested").
        The file_dict has id, name, createdTime, modifiedTime, webViewLink, parents.
        """
        root = folder_id or self._folder_id
        results: list[tuple[str, dict]] = []
        # Queue: list of (folder_id, relative_path)
        queue: list[tuple[str, str]] = [(root, "")]
        while queue:
            current_id, rel_path = queue.pop(0)
            # Files (Google Docs) in this folder
            files = self.list_files(folder_id=current_id, max_results=500)
            for f in files:
                results.append((rel_path, f))
            # Subfolders
            folders = self.list_folders(parent_id=current_id, max_results=500)
            for sub in folders:
                sub_path = f"{rel_path}/{sub['name']}" if rel_path else sub["name"]
                queue.append((sub["id"], sub_path))
        return results

    def list_files(
        self,
        folder_id: str | None = None,
        mime_type: str = "application/vnd.google-apps.document",
        max_results: int = 100,
    ) -> list[dict]:
        """List files in a folder (defaults to the configured shared folder).

        Args:
            folder_id: Drive folder ID. Defaults to GOOGLE_DRIVE_FOLDER_ID.
            mime_type: Filter by MIME type. Defaults to Google Docs.
            max_results: Maximum number of results.

        Returns:
            List of file resource dicts.
        """
        folder = folder_id or self._folder_id
        query_parts = [f"'{folder}' in parents", "trashed = false"]
        if mime_type:
            query_parts.append(f"mimeType = '{mime_type}'")
        query = " and ".join(query_parts)

        try:
            all_files: list[dict] = []
            page_token: str | None = None

            while True:
                result = (
                    self._drive.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, parents, createdTime, modifiedTime, webViewLink)",
                        pageSize=min(max_results - len(all_files), 100),
                        pageToken=page_token,
                        orderBy="modifiedTime desc",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                all_files.extend(result.get("files", []))
                page_token = result.get("nextPageToken")
                if not page_token or len(all_files) >= max_results:
                    break

            return all_files[:max_results]
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/list", method="GET", params={
                    "folder_id": folder, "max_results": str(max_results),
                })
            raise _wrap_http_error(e)

    def export_file(
        self, file_id: str, mime_type: str = "text/plain"
    ) -> bytes:
        """Export a Google Doc to a specified format.

        Args:
            file_id: The document ID.
            mime_type: Export MIME type. Common values:
                - text/plain
                - text/markdown
                - application/pdf
                - application/vnd.openxmlformats-officedocument.wordprocessingml.document

        Returns:
            The exported content as bytes.
        """
        try:
            return (
                self._drive.files()
                .export(fileId=file_id, mimeType=mime_type)
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                fmt_map = {
                    "application/pdf": "pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                    "text/html": "html",
                    "text/plain": "txt",
                    "text/markdown": "txt",
                }
                fmt = fmt_map.get(mime_type, "txt")
                result = self._mcp_request("docs/export", method="GET", params={
                    "document_id": file_id, "format": fmt,
                })
                # REST API returns text or base64 — convert to bytes for callers
                if isinstance(result, dict) and result.get("encoding") == "base64":
                    import base64
                    return base64.b64decode(result["data"])
                if isinstance(result, str):
                    return result.encode("utf-8")
                return json.dumps(result).encode("utf-8")
            raise _wrap_http_error(e)

    def copy_file(self, file_id: str, title: str | None = None) -> dict:
        """Copy a file, optionally renaming the copy.

        Args:
            file_id: The file to copy.
            title: Optional new title for the copy.

        Returns:
            The new file resource dict.
        """
        body: dict[str, Any] = {}
        if title:
            body["name"] = title
        if self._folder_id:
            body["parents"] = [self._folder_id]

        try:
            return (
                self._drive.files()
                .copy(fileId=file_id, body=body, fields="id, name, webViewLink",
                      supportsAllDrives=True)
                .execute()
            )
        except HttpError as e:
            raise _wrap_http_error(e)

    # ── Comments ──

    def add_comment(self, file_id: str, content: str) -> dict:
        """Add a comment to a file.

        Args:
            file_id: The file ID.
            content: The comment text.

        Returns:
            The comment resource dict.
        """
        try:
            return (
                self._drive.comments()
                .create(
                    fileId=file_id,
                    body={"content": content},
                    fields="id, content, author, createdTime, resolved",
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/comments", json_body={
                    "document_id": file_id, "content": content,
                })
            raise _wrap_http_error(e)

    def list_comments(self, file_id: str, include_resolved: bool = False) -> list[dict]:
        """List comments on a file.

        Args:
            file_id: The file ID.
            include_resolved: Whether to include resolved comments.

        Returns:
            List of comment resource dicts.
        """
        try:
            result = (
                self._drive.comments()
                .list(
                    fileId=file_id,
                    fields="comments(id, content, author, createdTime, resolved)",
                    includeDeleted=False,
                )
                .execute()
            )
            comments = result.get("comments", [])
            if not include_resolved:
                comments = [c for c in comments if not c.get("resolved")]
            return comments
        except HttpError as e:
            if e.resp.status == 403 and self._mcp_auth:
                _debug("403 from Google API — falling back to MCP Worker")
                return self._mcp_request("docs/comments", method="GET", params={
                    "document_id": file_id,
                    "include_resolved": str(include_resolved).lower(),
                })
            raise _wrap_http_error(e)

    def resolve_comment(self, file_id: str, comment_id: str) -> dict:
        """Mark a comment as resolved.

        Args:
            file_id: The file ID.
            comment_id: The comment ID.

        Returns:
            The updated comment resource dict.
        """
        try:
            return (
                self._drive.comments()
                .update(
                    fileId=file_id,
                    commentId=comment_id,
                    body={"resolved": True},
                    fields="id, content, author, createdTime, resolved",
                )
                .execute()
            )
        except HttpError as e:
            raise _wrap_http_error(e)


# Singleton
_client: DocsClient | None = None


def get_client() -> DocsClient:
    """Get the global client singleton."""
    global _client
    if _client is None:
        _client = DocsClient()
    return _client


def reset_client() -> None:
    """Reset the client singleton (for testing)."""
    global _client
    if _client is not None:
        _client.close()
    _client = None

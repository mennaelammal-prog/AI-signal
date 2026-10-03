"""Read-only connector for the existing scanalert REST API."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ScannerConnectorError(RuntimeError):
    """Raised when scanner alerts cannot be fetched safely."""


def fetch_scanner_alerts(
    base_url: str = "http://127.0.0.1:8000",
    *,
    status: str | None = "triggered",
    limit: int = 100,
    timeout_seconds: float = 5.0,
) -> list[dict[str, object]]:
    """Fetch scanner alerts using GET only.

    The connector intentionally exposes no POST/PUT/DELETE method and does not accept broker URLs.
    """
    if not base_url.startswith(("http://", "https://")):
        raise ScannerConnectorError("scanner base URL must use http or https")
    if limit < 1 or limit > 1000:
        raise ScannerConnectorError("limit must be between 1 and 1000")
    query = {"limit": str(limit)}
    if status:
        query["status"] = status
    url = f"{base_url.rstrip('/')}/api/alerts?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "signalforge-readonly/0.1"}, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - caller-supplied local/read-only URL
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ScannerConnectorError(f"unable to fetch scanner alerts: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ScannerConnectorError("scanner response must be a JSON array of alert objects")
    return payload  # type: ignore[return-value]

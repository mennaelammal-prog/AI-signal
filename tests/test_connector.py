import io
from unittest.mock import patch

import pytest

from signalforge.connector import ScannerConnectorError, fetch_scanner_alerts


def test_fetch_scanner_alerts_uses_get_and_parses_array():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'[{"event_id":"evt_1","paper_only":true}]'

    request = {}

    def fake_urlopen(req, timeout):
        request["method"] = req.method
        request["url"] = req.full_url
        request["timeout"] = timeout
        return Response()

    with patch("signalforge.connector.urlopen", fake_urlopen):
        result = fetch_scanner_alerts("http://127.0.0.1:8000", limit=10)
    assert result == [{"event_id": "evt_1", "paper_only": True}]
    assert request["method"] == "GET"
    assert "status=triggered" in request["url"]
    assert request["timeout"] == 5.0


def test_fetch_scanner_alerts_rejects_bad_response():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return io.BytesIO(b'{"not":"an array"}').read()

    with patch("signalforge.connector.urlopen", lambda *_args, **_kwargs: Response()), pytest.raises(
        ScannerConnectorError, match="JSON array"
    ):
        fetch_scanner_alerts()


def test_fetch_scanner_alerts_rejects_invalid_url_and_limit():
    with pytest.raises(ScannerConnectorError, match="http or https"):
        fetch_scanner_alerts("file:///tmp/scanner")
    with pytest.raises(ScannerConnectorError, match="between 1 and 1000"):
        fetch_scanner_alerts(limit=0)

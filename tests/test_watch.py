from unittest.mock import patch

import pytest

from signalforge import MarketContext, SignalForgeService, SignalStore
from signalforge.connector import ScannerConnectorError, fetch_scanner_health
from signalforge.watch import watch_scanner
from test_signalforge import alert, stats


def test_health_requires_paper_mode():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"paper_only": false, "trading_mode": "live"}'

    with patch("signalforge.connector.urlopen", lambda *_args, **_kwargs: Response()), pytest.raises(
        ScannerConnectorError, match="not paper-only"
    ):
        fetch_scanner_health()


def test_bounded_watch_polls_and_stops_cleanly():
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    events = []
    with patch("signalforge.watch.fetch_scanner_health", return_value={"paper_only": True, "trading_mode": "paper"}), patch(
        "signalforge.watch.poll_scanner_once", return_value=[service.process_alert(alert(), MarketContext(regime="trending_up"))]
    ):
        result = watch_scanner(
            service,
            interval_seconds=0.01,
            max_cycles=2,
            sleep_fn=lambda _seconds: None,
            on_cycle=events.append,
        )
    assert result["cycles"] == 2
    assert result["paper_only"] is True
    assert result["broker_submission"] is False
    assert len(events) == 2
    store.close()

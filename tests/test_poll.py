from dataclasses import asdict
from unittest.mock import patch

import pytest

from signalforge import MarketContext, SignalForgeService, SignalStore
from signalforge.connector import ScannerConnectorError
from signalforge.poll import load_stats_records, poll_scanner_once
from test_signalforge import alert, stats

PAPER_HEALTH = {"paper_only": True, "trading_mode": "paper"}


def test_poll_scanner_once_processes_read_only_alerts():
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    with patch("signalforge.poll.fetch_scanner_health", return_value=PAPER_HEALTH), patch(
        "signalforge.poll.fetch_scanner_alerts", return_value=[alert()]
    ):
        results = poll_scanner_once(
            service,
            scanner_url="http://127.0.0.1:8000",
            market=MarketContext(regime="trending_up"),
        )
    assert len(results) == 1
    assert results[0].paper_only is True
    assert store.count_signals() == 1
    store.close()


def test_poll_scanner_once_refuses_non_paper_scanner():
    """A single poll must refuse exactly like the continuous watch loop does --
    this was the gap: only watch_scanner checked health before this fix."""
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    with patch(
        "signalforge.poll.fetch_scanner_health",
        side_effect=ScannerConnectorError("scanner health is not paper-only; polling refused"),
    ), patch("signalforge.poll.fetch_scanner_alerts") as mock_alerts:
        with pytest.raises(ScannerConnectorError, match="not paper-only"):
            poll_scanner_once(service, scanner_url="http://127.0.0.1:8000")
    mock_alerts.assert_not_called()
    assert store.count_signals() == 0
    store.close()


def test_load_stats_records_validates_evidence():
    loaded = load_stats_records([asdict(stats())])
    assert loaded[0].strategy_id == "opening-range-breakout"

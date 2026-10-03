from dataclasses import asdict
from unittest.mock import patch

from signalforge import MarketContext, SignalForgeService, SignalStore
from signalforge.poll import load_stats_records, poll_scanner_once
from test_signalforge import alert, stats


def test_poll_scanner_once_processes_read_only_alerts():
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    with patch("signalforge.poll.fetch_scanner_alerts", return_value=[alert()]):
        results = poll_scanner_once(
            service,
            scanner_url="http://127.0.0.1:8000",
            market=MarketContext(regime="trending_up"),
        )
    assert len(results) == 1
    assert results[0].paper_only is True
    assert store.count_signals() == 1
    store.close()


def test_load_stats_records_validates_evidence():
    loaded = load_stats_records([asdict(stats())])
    assert loaded[0].strategy_id == "opening-range-breakout"

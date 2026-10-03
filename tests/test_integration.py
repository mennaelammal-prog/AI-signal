from signalforge import MarketContext, RiskContext, SignalForgeService, SignalStore
from test_signalforge import alert, stats


def test_service_persists_ranked_signal_once_and_summarizes():
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    result = service.process_alert(
        alert(),
        MarketContext(regime="trending_up", minutes_since_open=45),
        RiskContext(liquidity_dollar_volume=2_000_000, data_age_seconds=1),
    )
    assert result.status == "published"
    assert store.count_signals() == 1
    assert store.get_signal("evt_123")["event_id"] == "evt_123"
    duplicate = service.process_alert(alert(), MarketContext(regime="trending_up"))
    assert duplicate.candidate.event_id == "evt_123"
    assert store.count_signals() == 1
    summary = service.summary()
    assert summary == {"signals": 1, "published": 1, "qualified": 0, "rejected": 0, "paper_only": True, "broker_submission": False}
    store.close()


def test_service_preserves_rejection_when_strategy_evidence_missing():
    store = SignalStore(":memory:")
    result = SignalForgeService(store).process_alert(alert())
    assert result.status == "rejected_strategy_quality"
    assert store.list_signals()[0]["paper_only"] is True
    store.close()


def test_store_round_trips_persisted_strategy_evidence(tmp_path):
    path = tmp_path / "signals.db"
    store = SignalStore(path)
    original = stats()
    store.save_strategy_stats(original)
    loaded = store.get_strategy_stats(original.strategy_id, original.strategy_version)
    assert loaded == original
    store.close()

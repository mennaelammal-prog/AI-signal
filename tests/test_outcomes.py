import pytest

from signalforge import (
    MarketContext,
    OutcomeConfig,
    RiskContext,
    SignalForgeService,
    SignalStore,
    evaluate_signal,
)
from test_signalforge import alert, stats


def ranked(direction="long"):
    store = SignalStore(":memory:")
    store.save_strategy_stats(stats())
    service = SignalForgeService(store)
    result = service.process_alert(
        alert(direction=direction),
        MarketContext(regime="trending_up"),
        RiskContext(liquidity_dollar_volume=2_000_000, data_age_seconds=1),
    )
    return service, result


def test_long_target_outcome_uses_next_bar_open():
    service, signal = ranked()
    outcome = service.evaluate_outcome(
        signal,
        [
            {"bar_ts": "2026-09-30T14:29:00Z", "open": 25, "high": 25, "low": 25, "close": 25},
            {"bar_ts": "2026-09-30T14:31:00Z", "open": 25, "high": 25.5, "low": 24.9, "close": 25.4},
        ],
        OutcomeConfig(target_pct=1.5, stop_pct=0.75, max_hold_minutes=90),
    )
    assert outcome.exit_reason == "target"
    assert outcome.entry_price == 25.0
    assert outcome.pnl_pct > 0
    assert service.store.get_outcome(signal.candidate.event_id)["paper_only"] is True


def test_short_stop_outcome_is_loss():
    _service, signal = ranked("short")
    outcome = evaluate_signal(
        signal,
        [{"bar_ts": "2026-09-30T14:31:00Z", "open": 25, "high": 25.3, "low": 24.9, "close": 25.2}],
        OutcomeConfig(target_pct=1.5, stop_pct=0.75),
    )
    assert outcome.exit_reason == "stop"
    assert outcome.pnl_pct < 0


def test_ambiguous_bar_can_be_rejected():
    _service, signal = ranked()
    outcome = evaluate_signal(
        signal,
        [{"bar_ts": "2026-09-30T14:31:00Z", "open": 25, "high": 25.5, "low": 24.7, "close": 25}],
        OutcomeConfig(intrabar_policy="reject_ambiguous"),
    )
    assert outcome.exit_reason == "ambiguous_bar_rejected"
    assert outcome.pnl_pct == 0


def test_no_future_bars_is_rejected():
    _service, signal = ranked()
    with pytest.raises(ValueError, match="no future bars"):
        evaluate_signal(
            signal,
            [{"bar_ts": "2026-09-30T14:29:00Z", "open": 25, "high": 25, "low": 25, "close": 25}],
        )

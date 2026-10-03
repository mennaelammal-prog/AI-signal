from signalforge import CandidateSignal, MarketContext, RiskContext, SignalForgeEngine, StrategyStats
from signalforge.models import SignalValidationError


def alert(**overrides):
    base = {
        "event_id": "evt_123",
        "symbol": "ABCD",
        "strategy_id": "opening-range-breakout",
        "strategy_version": 3,
        "direction": "long",
        "event_type": "breakout",
        "source_timestamp": "2026-09-30T14:30:00Z",
        "detected_timestamp": "2026-09-30T14:30:01Z",
        "session": "regular",
        "trigger_price": 25.0,
        "bid": 24.99,
        "ask": 25.01,
        "spread_bps": 8.0,
        "feature_snapshot": {
            "rvol": 2.2,
            "vwap_dist_pct": 0.7,
            "orb_breakout_up": True,
            "dollar_volume": 2_000_000,
        },
        "filter_snapshot": {"config": {"config_hash": "abc"}},
        "data_provider": "alpaca",
        "data_feed": "iex",
        "paper_only": True,
        "hypothetical": True,
    }
    base.update(overrides)
    return base


def stats(**overrides):
    base = dict(
        strategy_id="opening-range-breakout",
        strategy_version=3,
        sample_size=120,
        expectancy_r=0.42,
        win_rate=0.58,
        profit_factor=1.7,
        max_drawdown_r=2.0,
        out_of_sample_expectancy_r=0.25,
        recent_expectancy_r=0.31,
        regime_expectancy_r={"trending_up": 0.5},
        time_bucket_expectancy={"morning": 0.4},
    )
    base.update(overrides)
    return StrategyStats(**base)


def test_adapts_scanner_alert_and_preserves_paper_boundary():
    candidate = CandidateSignal.from_scanner_alert(alert())
    assert candidate.symbol == "ABCD"
    assert candidate.paper_only is True
    assert candidate.hypothetical is True
    assert candidate.feature_snapshot["rvol"] == 2.2


def test_rejects_non_paper_event():
    try:
        CandidateSignal.from_scanner_alert(alert(paper_only=False))
    except SignalValidationError as exc:
        assert "paper-only" in str(exc)
    else:
        raise AssertionError("non-paper event was accepted")


def test_rank_is_explainable_and_paper_only():
    result = SignalForgeEngine().rank(
        CandidateSignal.from_scanner_alert(alert()),
        stats(),
        MarketContext(regime="trending_up", minutes_since_open=45, minutes_to_close=300, volatility_pct=3),
        RiskContext(liquidity_dollar_volume=2_000_000, data_age_seconds=1),
    )
    assert result.status == "published"
    assert result.quality_score > 55
    assert result.paper_only is True
    assert result.hypothetical is True
    assert any("Relative volume" in reason for reason in result.reasons)
    payload = result.as_dict()
    assert payload["label"] == "HYPOTHETICAL SIGNAL - PAPER ONLY - NOT AN ORDER"
    assert payload["score_components"]["total"] == result.quality_score


def test_spread_gate_rejects_before_publishing():
    result = SignalForgeEngine().rank(
        CandidateSignal.from_scanner_alert(alert(spread_bps=100)),
        stats(),
        risk=RiskContext(max_spread_bps=60, liquidity_dollar_volume=2_000_000, data_age_seconds=1),
    )
    assert result.status == "rejected_spread"
    assert result.quality_score == 0
    assert any("exceeds" in risk for risk in result.risks)


def test_missing_version_matched_stats_is_rejected():
    candidate = CandidateSignal.from_scanner_alert(alert())
    result = SignalForgeEngine().rank_many([candidate], {})[0]
    assert result.status == "rejected_strategy_quality"
    assert "version-matched" in result.risks[0]


def test_rank_many_is_deterministic_and_sorted():
    first = CandidateSignal.from_scanner_alert(alert(event_id="evt_a", symbol="ABCD"))
    second = CandidateSignal.from_scanner_alert(
        alert(event_id="evt_b", symbol="WXYZ", feature_snapshot={"rvol": 1.1, "dollar_volume": 300_000})
    )
    engine = SignalForgeEngine()
    kwargs = {
        "market": MarketContext(regime="trending_up", minutes_since_open=45),
        "risk_by_symbol": {
            "ABCD": RiskContext(liquidity_dollar_volume=2_000_000, data_age_seconds=1),
            "WXYZ": RiskContext(liquidity_dollar_volume=300_000, data_age_seconds=1),
        },
    }
    stats_by_strategy = {("opening-range-breakout", 3): stats()}
    one = [x.as_dict() for x in engine.rank_many([second, first], stats_by_strategy, **kwargs)]
    two = [x.as_dict() for x in engine.rank_many([second, first], stats_by_strategy, **kwargs)]
    assert one == two
    assert one[0]["symbol"] == "ABCD"


def test_stale_data_is_rejected_and_invalidation_is_present():
    candidate = CandidateSignal.from_scanner_alert(alert())
    stale = SignalForgeEngine().rank(
        candidate,
        stats(),
        risk=RiskContext(data_age_seconds=30, stale_after_seconds=15, liquidity_dollar_volume=2_000_000),
    )
    assert stale.status == "rejected_stale_data"
    assert stale.invalidation_conditions

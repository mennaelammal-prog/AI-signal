# SignalForge AI — First Implementation Slice

## Current status

Implemented in `src/signalforge/`:

- Scanner-alert adapter that accepts the existing `scanalert.AlertEvent` JSON shape without importing the scanner package.
- Strict paper-only and hypothetical-event validation.
- Versioned candidate-signal contract.
- Strategy-evaluation evidence contract.
- Market and risk context contracts.
- Transparent deterministic baseline scoring.
- Spread, liquidity, stale-data, correlation, daily-risk, and missing-evidence gates.
- Ranked signal output with persisted score components.
- Structured reasons, risks, and invalidation conditions.
- Deterministic multi-signal ranking.
- Seven unit tests covering validation, ranking, gates, determinism, and paper-only labeling.

## Integration boundary

The first slice does not change the existing scanner. It consumes a serialized scanner alert, such as the output of `GET /api/alerts` from the scanner repository.

The adapter expects the scanner event to contain:

```json
{
  "event_id": "evt_...",
  "symbol": "ABCD",
  "strategy_id": "opening-range-breakout",
  "strategy_version": 3,
  "direction": "long",
  "event_type": "breakout",
  "source_timestamp": "2026-09-30T14:30:00Z",
  "detected_timestamp": "2026-09-30T14:30:01Z",
  "session": "regular",
  "trigger_price": 25.0,
  "spread_bps": 8.0,
  "feature_snapshot": {"rvol": 2.2, "vwap_dist_pct": 0.7},
  "paper_only": true,
  "hypothetical": true
}
```

Real provider identity is preserved in `data_provider` and `data_feed`, but this package does not open a market-data connection itself yet. The scanner remains responsible for provider ingestion, timestamps, corrections, reconnects, and alert lifecycle.

## Baseline scoring

The baseline score is intentionally explainable and is not a probability or forecast. Its components are:

- Strategy evidence: expectancy, out-of-sample expectancy, and sample maturity.
- Feature alignment: relative volume, VWAP alignment, and breakout context.
- Liquidity quality: dollar-volume evidence.
- Regime compatibility: point-in-time strategy expectancy for the current regime.
- Timing: point-in-time expectancy for the current session bucket.
- Penalties: spread, volatility, correlation, drawdown, and stale-data penalties.

Every component is available in `RankedSignal.as_dict()`.

## Usage example

```python
from signalforge import CandidateSignal, MarketContext, RiskContext, SignalForgeEngine, StrategyStats

candidate = CandidateSignal.from_scanner_alert(scanner_alert_json)
evidence = StrategyStats(
    strategy_id=candidate.strategy_id,
    strategy_version=candidate.strategy_version,
    sample_size=120,
    expectancy_r=0.42,
    win_rate=0.58,
    profit_factor=1.7,
    max_drawdown_r=2.0,
    out_of_sample_expectancy_r=0.25,
    regime_expectancy_r={"trending_up": 0.5},
    time_bucket_expectancy={"morning": 0.4},
)
ranked = SignalForgeEngine().rank(
    candidate,
    evidence,
    MarketContext(regime="trending_up", minutes_since_open=45),
    RiskContext(liquidity_dollar_volume=2_000_000, data_age_seconds=1),
)
print(ranked.as_dict())
```

The returned record remains:

```text
HYPOTHETICAL SIGNAL - PAPER ONLY - NOT AN ORDER
```

## Next implementation slice

The next step should be a read-only integration service that fetches scanner alerts and point-in-time strategy evaluation records, then persists SignalForge results. It should be added only after agreeing on storage and authentication boundaries. No broker adapter or live order path belongs in this slice.

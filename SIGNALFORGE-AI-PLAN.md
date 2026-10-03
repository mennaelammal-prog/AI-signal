# SignalForge AI — Planned Second System

## Purpose

SignalForge AI is the planned second system built on top of the existing paper-only scanner and alert platform. It will rank, explain, and evaluate candidate signals rather than replace the deterministic scanner.

## Safety boundary

SignalForge AI will remain paper-only and simulation-only. It will not place, transmit, modify, cancel, or route live financial orders. Every signal, entry, fill, return, and balance will be labeled hypothetical, simulated, paper, or backtested.

## Product distinction

The existing scanner answers: “Did this symbol meet the configured conditions?”

SignalForge AI answers: “Among the candidates that triggered, which signals have better support from historical evidence, current market context, liquidity, risk, and strategy quality?”

The architecture is:

```text
Market data
    |
    v
Deterministic scanner
    |
    v
Candidate signals
    |
    v
SignalForge ranking and interpretation
    |
    v
Risk and quality gates
    |
    v
Ranked paper-only signals
    |
    +--> Alert UI
    +--> Signal explanation
    +--> Paper simulation
    +--> Backtest evaluation
```

## Planned components

### Candidate Signal Service

Consume immutable scanner events and preserve symbol, direction, strategy ID/version, alert type, timestamps, trigger price, bid/ask, spread, relative volume, VWAP distance, volatility, session, market regime, data freshness, and feature snapshot.

### Feature and Context Engine

Calculate symbol-level, market-level, and signal-quality features. Each feature must preserve its name, unit, timestamp, source, lookback, null policy, and version.

Candidate features include gap percentage, relative volume, volume acceleration, price/range position, VWAP distance, opening-range relationship, ATR, spread, dollar volume, market breadth, index direction, sector performance, volatility regime, strategy expectancy, time-of-day performance, spread-bucket performance, and current correlation/exposure.

### Strategy Evaluation Service

Track trade count, win rate, average winner/loser, expectancy, profit factor, maximum drawdown, holding time, performance by time, volatility regime, spread bucket, market regime, recent rolling performance, out-of-sample performance, and forward paper-validation performance.

Maintain separate training, validation, out-of-sample, and forward-paper periods.

### Signal Ranking

Start with a transparent deterministic score:

```text
Signal score =
    strategy expectancy
  + feature alignment
  + liquidity quality
  + market-regime compatibility
  + historical time-of-day quality
  - spread penalty
  - volatility penalty
  - correlation penalty
  - recent drawdown penalty
  - stale-data penalty
```

Persist every score component. Do not begin with a black-box model. Later candidates may include logistic regression or calibrated gradient-boosted ranking models, but they must be compared against the transparent baseline and remain explainable.

### Market-Regime Classifier

Begin with explicit measurable regimes such as trending up, trending down, range-bound, high volatility, low volatility, weak breadth, strong breadth, opening transition, midday compression, and closing expansion.

### Signal Interpretation

Generate explanations from structured facts, not invented commentary. Each explanation must state:

1. Why the signal triggered.
2. Supporting factors.
3. Weakening factors.
4. Historical evidence.
5. Modeled entry, stop, and target.
6. Invalidation conditions.
7. Missing or stale data.

Persist the feature snapshot, score components, model/version, explanation template or prompt version, and generated explanation.

### Signal Lifecycle

```text
candidate -> qualified -> ranked -> published -> paper_entry_proposed
          -> paper_filled -> target_hit | stop_hit | timed_exit
          -> invalidated | expired -> evaluated
```

Preserve rejected states such as `rejected_spread`, `rejected_liquidity`, `rejected_stale_data`, `rejected_market_regime`, `rejected_correlation`, `rejected_daily_risk`, and `rejected_strategy_quality`.

## Build phases

1. **Audit and integration:** inspect the existing scanner event schema, feature availability, alert persistence, strategy versioning, backtest outputs, paper-fill interfaces, WebSocket events, database, API, and safety guards.
2. **Domain model:** add candidate signals, features, scores, explanations, strategy evaluations, market regimes, model versions, outcomes, and rejection records.
3. **Deterministic features:** implement and test all features using fixture data first.
4. **Strategy evaluation:** add training/validation/out-of-sample splits, rolling evaluation, regimes, cost/slippage sensitivity, parameter sensitivity, and minimum-sample warnings.
5. **Ranking:** implement transparent scoring, components, thresholds, tie-breaking, correlation checks, and exposure checks.
6. **Interpretation:** build structured explanations with supporting and weakening factors and data-quality warnings.
7. **UI:** add separate SignalForge Dashboard, Signal Feed, Signal Explanation, Strategy Intelligence, Model History, and Outcome Review screens.
8. **Paper validation:** run shadow mode first, then paper simulation with simulated entries, stops, targets, exits, spread, slippage, latency, and reconciliation.
9. **Verification:** test determinism, look-ahead prevention, versioning, stale data, missing data, duplicate alerts, real-time/backtest feature consistency, Windows scripts, migrations, and paper-only safety.

## Definition of done

- Immutable candidate signals are created from scanner events.
- Features are versioned and traceable to raw inputs.
- Market regimes are measurable and documented.
- Signals are ranked with persisted score components.
- Every explanation traces to structured evidence.
- Rejected signals remain available for analysis.
- Entry, stop, target, and invalidation levels are hypothetical and reproducible.
- Strategy evaluation separates in-sample, validation, out-of-sample, and paper periods.
- UI displays ranked signals and explanations.
- Model, strategy, feature, and data versions are preserved.
- Look-ahead prevention has automated tests.
- Stale and missing-data behavior has automated tests.
- No live order path exists.
- The application remains labeled `PAPER ONLY` and `SIMULATED`.

## Reference sources

- https://www.trade-ideas.com/learning-center/ai-in-trading/how-holly-ai-generates-trade-signals/
- https://www.trade-ideas.com/hollyguide/Holly_Windows.html
- https://www.trade-ideas.com/hollyguide/AI_Holly_Strategy_Window.html
- https://www.trade-ideas.com/hollyguide/AI_Holly_Strategy_Trades_Window.html
- https://www.trade-ideas.com/guide/chapter/14_9_7/14.9.7Show_AI_Trades.html
- https://www.trade-ideas.com/hollyguide/Holly_History.html
- https://www.trade-ideas.com/hollyguide/AI_Long_Term_Strategy_Trades_Window.html
- https://www.trade-ideas.com/ti-ai-virtual-trade-assistant/
- https://www.trade-ideas.com/learning-center/backtesting-strategy-development/oddsmaker-backtesting-guide/
- https://www.trade-ideas.com/learning-center/backtesting-strategy-development/how-to-evaluate-a-trading-strategy/
- https://docs.alpaca.markets/docs/real-time-stock-pricing-data
- https://docs.alpaca.markets/us/docs/streaming-market-data
- https://www.nyse.com/markets/hours-calendars

These sources describe public behavior and engineering considerations. They do not reveal proprietary Holly model code or provide a public Holly signal API.

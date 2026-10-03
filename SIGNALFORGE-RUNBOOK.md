# SignalForge AI — Local Paper-Validation Runbook

## What is complete

This repository now contains a usable first release of SignalForge:

- `signalforge.models`: validated scanner-event, context, strategy-evidence, score, and ranked-signal contracts.
- `signalforge.scoring`: deterministic explainable baseline ranking and quality gates.
- `signalforge.store`: SQLite persistence for strategy evidence and immutable ranked signals.
- `signalforge.service`: read-only scanner-alert ingestion service.
- `signalforge.connector`: GET-only connector for the scanner's `/api/alerts` endpoint.
- `signalforge.outcomes`: deterministic hypothetical target/stop/time-exit evaluation over supplied OHLC bars.
- `signalforge.web`: read-only local dashboard and JSON endpoints.
- `signalforge.cli`: local JSON/JSON-lines processing command.

The implementation has no broker package, no order endpoint, and no live-trading path.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

On Linux/macOS:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Prepare inputs

`--alerts` accepts either a JSON array or JSON-lines file containing the existing scanner alert contract. The scanner event must have `paper_only: true` and `hypothetical: true`.

`--stats` is a JSON array of version-matched strategy evaluation records. Evidence must be point-in-time: do not calculate it with bars after the signal timestamp.

Example strategy evidence:

```json
[
  {
    "strategy_id": "opening-range-breakout",
    "strategy_version": 3,
    "sample_size": 120,
    "expectancy_r": 0.42,
    "win_rate": 0.58,
    "profit_factor": 1.7,
    "max_drawdown_r": 2.0,
    "out_of_sample_expectancy_r": 0.25,
    "recent_expectancy_r": 0.31,
    "regime_expectancy_r": {"trending_up": 0.5},
    "time_bucket_expectancy": {"morning": 0.4}
  }
]
```

## Run ranking

```powershell
signalforge rank `
  --alerts .\alerts.jsonl `
  --stats .\strategy-stats.json `
  --db .\data\signalforge.db `
  --market .\market-context.json `
  --output .\data\ranked-signals.json
```

The output includes:

- `summary`
- `quality_score`
- individual score components
- status (`published`, `qualified`, or a rejection state)
- supporting reasons
- risk deductions
- invalidation conditions
- model and feature versions
- `paper_only: true`
- `hypothetical: true`
- `broker_submission: false`

## Evaluate paper outcomes

The outcome evaluator uses the first bar strictly after the signal timestamp as the modeled entry. It supports target, stop, time exit, commission/slippage deductions, and explicit intrabar policies: `stop_first`, `target_first`, or `reject_ambiguous`. It never uses a broker position and never submits an order.

Use `SignalForgeService.evaluate_outcome(result, future_bars, OutcomeConfig(...))` from a controlled Python process. Future bars must contain `bar_ts`, `open`, `high`, `low`, and `close`. Results are stored in the `paper_outcomes` SQLite table and included in the service summary.

## Local review dashboard

After producing a SQLite database:

```powershell
signalforge serve --db .\data\signalforge.db --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. The dashboard is read-only and exposes only:

- `/` — ranked signal review
- `/api/summary` — signal and paper-outcome counts
- `/api/signals` — ranked signal JSON

There are no mutation routes, broker routes, or order routes.

## Scanner integration

The existing scanner API returns alerts from `GET /api/alerts`. The `fetch_scanner_alerts` connector fetches that endpoint with GET only, validates that the response is a JSON array, and passes records to `SignalForgeService.process_alerts`. It has no POST, PUT, DELETE, broker, or order method. The CLI remains file-based so the operator can inspect the input before processing.

The integration must preserve:

- scanner event ID
- source and detection timestamps
- strategy ID/version
- feature snapshot
- provider/feed identity
- paper-only labels

Do not merge the SignalForge score back into the scanner’s immutable alert record. Store it as a separate result linked by `event_id`.

## Operational rules

- Do not set `paper_only` or `hypothetical` to false.
- Do not add live credentials or live broker URLs.
- Do not interpret `quality_score` as probability, expected return, or a recommendation.
- Do not publish a signal when its version-matched strategy evidence is missing.
- Preserve rejected signals for audit and calibration.
- Keep model, feature, strategy, and data versions with every result.
- Use out-of-sample and forward paper validation before judging usefulness.

## Validation

```bash
PYTHONPATH=src python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
```

The current release also tests duplicate event handling, stale-data rejection, spread gates, missing-evidence rejection, SQLite round trips, deterministic sorting, and paper-only output labels.

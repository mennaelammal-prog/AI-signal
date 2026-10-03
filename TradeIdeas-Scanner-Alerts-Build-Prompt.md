# Master Build Prompt: Real-Time Stock Scanner and Alert Platform

You are the lead software engineer responsible for designing, implementing, testing, documenting, and delivering a complete paper-only real-time stock scanner and alert platform.

Do not stop at architecture or a partial prototype. Inspect the existing workspace first, then implement the system end-to-end. Continue working through coding, configuration, migrations, tests, debugging, documentation, and local verification until the system is complete and runnable. Do not repeatedly return to ask for confirmation about ordinary implementation choices. Make reasonable, reversible engineering decisions and record them in the documentation.

Only stop and ask the user a question if one of these genuine blockers occurs:

1. A required credential, API key, account permission, licensed data feed, or external service is missing.
2. A requested action would submit, route, modify, cancel, or transmit a live financial order.
3. A PowerShell command must be run by the user because the environment prevents the AI from executing it.
4. The repository contains a material conflict that cannot be resolved without the user's decision.
5. The system cannot be safely tested without user-owned Windows, broker, or market-data access.

If a PowerShell command is required, write the exact command into a clearly named `.ps1` file and also show the exact command to run. Explain what it does, what directory it must be run from, expected output, and how to verify success. Do not ask the user to copy partial commands from a long explanation. Prefer executing commands yourself when the current environment permits it.

## Non-negotiable safety boundary

Build and test a **paper-only, simulation-only system**. Do not connect to a live brokerage account, live order endpoint, live trading credential, or live order-routing interface. Do not place, modify, cancel, transmit, sign, or submit any financial order.

The product may generate analysis, scanner events, alerts, hypothetical entries, paper fills, backtests, and unsubmitted order intents. Every result must be clearly labeled as hypothetical, simulated, paper, or backtested.

Implement a fail-closed environment guard:

- Default environment: `paper`.
- Reject any live endpoint or live credential.
- Require an explicit configuration value such as `TRADING_MODE=paper`.
- Refuse startup if a live broker URL is detected.
- Keep paper and live credentials physically and logically separate.
- Do not implement a live-trading escape hatch in this project.

## Product objective

Build a web application and backend that can:

1. Ingest real-time stock trades, quotes, and bars from a supported market-data provider.
2. Maintain a clean internal market-data model with timestamps, sessions, corrections, and reconnect handling.
3. Scan a configurable stock universe using typed filters and formulas.
4. Produce event-driven real-time alerts.
5. Produce ranked Top List snapshots separately from event alerts.
6. Display alert history, current candidates, strategy details, and charts or chart links.
7. Send local/browser notifications and optional non-transactional notifications.
8. Replay historical data through the same scanner logic for backtesting.
9. Generate paper-only hypothetical entries, exits, stops, targets, and simulated fills.
10. Provide a test suite, seed data, API documentation, setup instructions, and operational runbooks.

The target behavior should be inspired by the documented Trade Ideas concepts, but do not scrape Trade Ideas, bypass access controls, infer undocumented APIs, or claim compatibility with proprietary Trade Ideas internals.

## Default technical choices

Use these defaults unless the existing repository already has a strong, compatible architecture:

- Backend: Python 3.11+ with FastAPI.
- Real-time transport: WebSocket endpoint from backend to browser clients.
- Market-data ingestion: provider adapter interface with one concrete paper/development adapter.
- Database: PostgreSQL-compatible schema. If PostgreSQL is unavailable locally, provide a SQLite development fallback without changing the domain model.
- Frontend: React with TypeScript if a frontend already exists; otherwise create a simple responsive browser UI with the repository's existing frontend conventions.
- Background jobs: a clear worker process or asyncio task group with graceful shutdown.
- Configuration: `.env.example`, typed settings, and explicit paper-mode checks.
- Testing: pytest for backend; frontend tests using the existing project test framework.
- Packaging: `pyproject.toml` or the repository's existing package manager.
- Windows support: provide PowerShell setup, migration, test, run, and stop scripts.
- Container support: add Docker Compose only if it improves reproducibility and does not replace a native Windows development path.

Do not add unnecessary infrastructure. Favor a reliable small system over a large microservice architecture.

## Required system components

### 1. Configuration and environment safety

Implement:

- Typed settings object.
- `.env.example` with safe placeholder values.
- `TRADING_MODE=paper` default.
- `DATA_PROVIDER` selection.
- Paper endpoint validation.
- Startup refusal for live broker URLs, live trading flags, or live credential names.
- Health endpoint showing data-provider status, market session, last event time, and paper-only mode.
- Redacted configuration diagnostics.

### 2. Market-data adapter

Create an interface such as:

```python
class MarketDataProvider(Protocol):
    async def subscribe_trades(self, symbols: list[str]) -> None: ...
    async def subscribe_quotes(self, symbols: list[str]) -> None: ...
    async def subscribe_bars(self, symbols: list[str], timeframe: str) -> None: ...
    async def historical_bars(self, request: HistoricalBarsRequest) -> list[Bar]: ...
    async def health(self) -> ProviderHealth: ...
```

The adapter must normalize provider events into internal models:

- Trade
- Quote/NBBO
- Minute bar
- Updated/corrected bar
- Market session event
- Trading halt/resume event if available
- Provider error/reconnect event

Store both provider timestamp and local ingestion timestamp. Preserve raw events when practical for replay and debugging.

Implement:

- Authentication handling without logging secrets.
- WebSocket reconnect with exponential backoff.
- Resubscription after reconnect.
- Heartbeat or stale-stream detection.
- Backpressure handling.
- Duplicate-event protection.
- Late and corrected event handling.
- Provider rate-limit handling.
- Data-gap diagnostics.

Use a development adapter that can replay fixtures even if no external data credential is available.

### 3. Market sessions and symbol universe

Implement explicit session handling:

- US Eastern Time normalization.
- Regular session: 09:30–16:00 ET.
- Configurable premarket and postmarket flags, disabled by default for OddsMaker-style backtests.
- Holidays and early closes through an exchange-calendar abstraction.
- Symbol activation/deactivation.
- Delisted or invalid-symbol handling.
- Configurable universe source.
- Point-in-time universe support in the backtest interface.

Do not hard-code weekdays as the complete market calendar.

### 4. Typed filter and formula engine

Implement a safe, versioned filter model. A filter must include:

- `id`
- `name`
- `version`
- `field`
- `operator`
- `value`
- `unit`
- `session_basis`
- `lookback`
- `null_policy`
- `enabled`
- `description`

Support at least:

- Last price
- Bid and ask
- Spread and spread percentage
- Volume
- Relative volume
- Percent change
- Dollar change
- High/low range
- VWAP distance
- Opening-range breakout
- New high/new low events
- Moving-average relationship
- Volatility
- Time-of-day
- Minimum liquidity and maximum spread

Implement a constrained formula language or AST. Do not execute arbitrary Python, JavaScript, PowerShell, SQL, or shell code supplied by a user.

Support:

- Numeric operators
- Boolean AND/OR/NOT
- Comparisons
- Bounded lookbacks
- Basic conditional expressions
- Unit and type validation
- Divide-by-zero handling
- Null handling
- Formula versioning
- Clear validation errors

Use deterministic filter evaluation and preserve the exact filter/formula configuration with every alert and backtest run.

### 5. Scanner engine

Create separate scanner modes:

#### Event scanner

Emits an alert when a condition transitions into a triggered state. Prevent repeated alerts using configurable cooldown and deduplication rules.

#### Snapshot scanner

Periodically evaluates all symbols, ranks qualifying symbols, and returns a Top List. Make refresh interval and maximum rows configurable.

Support:

- Multiple strategies.
- AND-combined filters within a strategy.
- OR-combined alert conditions.
- Server-side ranking.
- Secondary display sorting.
- Strategy enable/disable.
- Scan preview against fixture data.
- Deterministic tie-breaking.
- Strategy versioning.

Every signal/event must contain:

```json
{
  "event_id": "stable-unique-id",
  "symbol": "ABC",
  "strategy_id": "opening-range-breakout",
  "strategy_version": 1,
  "direction": "long",
  "event_type": "breakout",
  "source_timestamp": "ISO-8601",
  "detected_timestamp": "ISO-8601",
  "session": "regular",
  "trigger_price": 12.34,
  "bid": 12.33,
  "ask": 12.35,
  "spread_bps": 16.2,
  "feature_snapshot": {},
  "filter_snapshot": {},
  "status": "triggered",
  "paper_only": true
}
```

### 6. Alert state machine and notifications

Implement alert states:

- `working`
- `triggered`
- `invalidated`
- `expired`
- `acknowledged`
- `suppressed`

Build:

- Alert persistence.
- Alert history.
- Deduplication.
- Cooldowns.
- Priority levels.
- User preferences.
- Quiet hours.
- Retry handling.
- Notification audit log.
- Browser/WebSocket notifications.
- Optional email/webhook abstraction that remains disabled by default.
- A test notification button that never sends a financial order.

Use the source event timestamp and delivery timestamp separately. Display stale-data and delayed-delivery warnings.

### 7. Paper-entry and simulated-fill module

Do not build live order routing. Build only hypothetical paper intents and fills.

When an alert triggers, allow the user to generate a paper entry proposal containing:

- Symbol
- Direction
- Hypothetical quantity or risk-based quantity
- Entry model
- Stop model
- Target model
- Time exit
- Estimated spread
- Estimated slippage
- Maximum modeled loss
- Strategy version
- Expiration

Implement a fill simulator with configurable models:

- Next available trade.
- Next bar open.
- Bid/ask crossing.
- Fixed slippage.
- Spread-plus-slippage.
- Partial fill simulation.
- Rejection due to stale data or liquidity.

Every fill must be labeled `simulated=true` and must never be sent to a broker.

### 8. OddsMaker-style backtest engine

Use the same strategy/filter code as live scanning wherever possible.

Implement:

- Historical 1-minute bar replay.
- Chronological alert processing.
- Configurable regular-session window.
- Optional one-entry-per-symbol-per-day rule.
- Configurable daily trade cap.
- Entry direction.
- Dollar or percent move units.
- Fixed-time exits.
- Time-after-entry exits.
- Same-day close fallback.
- Next-day open/close exits.
- Profit target.
- Stop loss.
- Trailing stop.
- Alert-based exit.
- Commission and fee assumptions.
- Spread and slippage assumptions.
- Position sizing.
- Starting equity.
- Maximum concurrent positions.
- Daily loss limit.
- Buying-power requirement.

Make intrabar ambiguity explicit. If a bar's high and low could trigger both stop and target, use a configurable policy such as conservative stop-first, target-first, or reject-as-ambiguous. Report the selected policy in the result.

Backtest reports must include:

- Total trades.
- Win rate.
- Profit factor.
- Expectancy.
- Average winner.
- Average loser.
- Gross P&L.
- Net P&L.
- Maximum drawdown.
- Equity curve.
- Daily P&L.
- Trades per day.
- Buying-power peak.
- Holding-time distribution.
- Exit-reason distribution.
- Consecutive wins/losses.
- Slippage and cost totals.
- Filter/feature attribution.
- Date range and actual data coverage.
- Strategy/filter version.
- Data provider and feed.
- All assumptions.

Clearly label all backtest values as historical simulations, not predictions or guarantees.

### 9. Web UI

Build a usable UI with these screens:

1. Dashboard: market session, provider health, alert count, recent events, and paper-only status.
2. Scanner builder: strategy name, filters, formulas, ranking, session, and preview.
3. Live alerts: streaming rows, priority, status, trigger details, and acknowledgement.
4. Top Lists: ranked snapshot with refresh time and data freshness.
5. Alert detail: feature snapshot, filter evaluation, chart link or local chart, and paper-entry proposal.
6. Backtest runner: strategy, universe, date range, session, exits, costs, slippage, and fill policy.
7. Backtest report: metrics, equity curve, daily P&L, drawdown, trade list, and assumptions.
8. Settings: provider, symbols, notification preferences, paper mode, and data health.

Use clear labels such as `PAPER ONLY`, `SIMULATED`, `BACKTEST`, `DATA DELAY`, and `STALE FEED`.

### 10. API and event contracts

Document and implement endpoints similar to:

```text
GET  /health
GET  /api/config/public
GET  /api/strategies
POST /api/strategies
PUT  /api/strategies/{id}
POST /api/strategies/{id}/validate
POST /api/strategies/{id}/preview
GET  /api/alerts
GET  /api/alerts/{event_id}
POST /api/alerts/{event_id}/acknowledge
GET  /api/top-lists/{strategy_id}
POST /api/backtests
GET  /api/backtests/{run_id}
GET  /api/backtests/{run_id}/trades
GET  /api/paper-positions
POST /api/paper-intents
WS   /ws/alerts
WS   /ws/market-status
```

The `POST /api/paper-intents` endpoint must create a simulated intent only. It must not call any broker order endpoint.

Use OpenAPI documentation and include JSON examples for all important event types.

### 11. Database model

Create migrations and indexes for at least:

- `symbols`
- `market_sessions`
- `raw_market_events`
- `quotes`
- `trades`
- `bars`
- `strategies`
- `strategy_versions`
- `filters`
- `formula_versions`
- `alert_events`
- `alert_deliveries`
- `backtest_runs`
- `backtest_trades`
- `paper_intents`
- `paper_fills`
- `audit_log`

All strategy, alert, and backtest records must preserve their configuration version and data-source metadata.

### 12. Testing requirements

Implement tests before declaring completion.

#### Unit tests

- Filter operators.
- Formula validation.
- Null and divide-by-zero behavior.
- Session boundaries.
- Early closes and holidays.
- Relative-volume calculations.
- VWAP and range calculations.
- Alert state transitions.
- Deduplication and cooldowns.
- Ranking and tie-breaking.
- Stop/target collision policy.
- Slippage and spread calculations.
- Position sizing.
- Daily loss limits.
- Paper-mode safety guard.

#### Integration tests

- Provider fixture replay into scanner.
- WebSocket alert delivery.
- Reconnect and resubscribe.
- Corrected/late event handling.
- Database persistence.
- Backtest run creation and report generation.
- Paper-intent creation without broker calls.

#### End-to-end tests

- Create a strategy.
- Validate it.
- Run it against fixture market data.
- Receive a live-style alert.
- Acknowledge the alert.
- Generate a paper intent.
- Run a backtest.
- View the report.

Add a test that fails if any live broker URL or live trading credential is detected.

### 13. PowerShell scripts

Create and document these scripts if the project runs on Windows:

- `scripts/setup.ps1`
- `scripts/install.ps1`
- `scripts/migrate.ps1`
- `scripts/test.ps1`
- `scripts/run-backend.ps1`
- `scripts/run-frontend.ps1`
- `scripts/run-dev.ps1`
- `scripts/stop-dev.ps1`
- `scripts/seed-fixtures.ps1`
- `scripts/run-smoke-test.ps1`

Each script must:

- Use strict error handling.
- Print the current directory and key configuration mode.
- Fail clearly when dependencies are missing.
- Never print secrets.
- Default to paper-only mode.
- Include a safe dry-run or status mode when appropriate.

### 14. Documentation deliverables

Create:

- `README.md`
- `ARCHITECTURE.md`
- `API.md`
- `DATA_MODEL.md`
- `BACKTEST_METHODOLOGY.md`
- `PAPER_TRADING_SAFETY.md`
- `POWER_SHELL_SETUP.md`
- `.env.example`
- `CHANGELOG.md`

The README must contain exact setup, migration, test, run, stop, and troubleshooting instructions.

The backtest documentation must disclose:

- 1-minute OHLC limitations.
- Intrabar ambiguity policy.
- Spread/slippage/commission assumptions.
- Data coverage and provider.
- Corporate-action and universe policy.
- Session-calendar policy.
- Survivorship and look-ahead controls.
- Paper-fill limitations.

## Source material to use and cite

Use these official sources as behavioral references and cite them in the project documentation:

### Trade Ideas

- Alert Window: https://www.trade-ideas.com/guide/chapter/9/9Alert_Window.html
- Top List Window: https://www.trade-ideas.com/guide/chapter/10/10Top_List_Window.html
- Sort Tab: https://www.trade-ideas.com/guide/chapter/10_2_7/10.2.7Sort_Tab.html
- Layouts & Scans: https://www.trade-ideas.com/guide/chapter/29/29Layouts_and_Scans.html
- Filter Codes: https://www.trade-ideas.com/AccountManagement/FilterCodes.html
- Formula Editor: https://www.trade-ideas.com/guide/chapter/8_3_3_1/8.3.3.1Formula_Editor.html
- Price Filter: https://www.trade-ideas.com/help/filter/Price/
- Backtesting/Oddsmaker: https://www.trade-ideas.com/guide/chapter/22/22Backtesting_Oddsmaker.html
- OddsMaker User's Guide v2: https://www.trade-ideas.com/OddsMaker/Help.version2.html
- Entry Tab: https://www.trade-ideas.com/guide/chapter/22_1/22.1Entry_Tab.html
- Timed Exit Tab: https://www.trade-ideas.com/guide/chapter/22_2/22.2Timed_Exit_Tab.html
- Risk Management Tab: https://www.trade-ideas.com/guide/chapter/22_3/22.3Risk_Management_Tab.html
- Advanced Exit Tab: https://www.trade-ideas.com/guide/chapter/22_4/22.4Advanced_Exit_Tab.html
- OddsMaker Backtesting Guide: https://www.trade-ideas.com/learning-center/backtesting-strategy-development/oddsmaker-backtesting-guide/
- How to Evaluate a Trading Strategy: https://www.trade-ideas.com/learning-center/backtesting-strategy-development/how-to-evaluate-a-trading-strategy/
- Holly AI signal generation: https://www.trade-ideas.com/learning-center/ai-in-trading/how-holly-ai-generates-trade-signals/
- Holly Windows: https://www.trade-ideas.com/hollyguide/Holly_Windows.html
- AI Holly Strategy Window: https://www.trade-ideas.com/hollyguide/AI_Holly_Strategy_Window.html
- AI/Holly Strategy Trades Window: https://www.trade-ideas.com/hollyguide/AI_Holly_Strategy_Trades_Window.html
- Show AI Trades: https://www.trade-ideas.com/guide/chapter/14_9_7/14.9.7Show_AI_Trades.html
- Audible Trade Notifications: https://www.trade-ideas.com/hollyguide/Trade_Notifications.html
- External Linking: https://www.trade-ideas.com/guide/chapter/8_3_2/8.3.2External_Linking.html
- One-Click Order Entry Template: https://www.trade-ideas.com/guide/chapter/21_4_2_1/21.4.2.1Create_a_OneClick_Order_Entry_Template_.html
- Auto-Trading Strategy guide: https://www.trade-ideas.com/guide/chapter/21_4_2_2/21.4.2.2Create_an_AutoTrading_Strategy_.html
- Stop/Limit/Stop-Market guide: https://www.trade-ideas.com/guide/chapter/21_4_2_3/21.4.2.3How_to_use_Stop_Limit_and_Stop_Market_Orders_as_Entry_Orders_.html
- Interactive Brokers connection: https://www.trade-ideas.com/guide/chapter/21_1_2/21.1.2Connect_to_Interactive_Brokers.html
- Features: https://www.trade-ideas.com/features/
- Brokers: https://www.trade-ideas.com/brokers/

### Market-data and paper environments

- Alpaca real-time stock data: https://docs.alpaca.markets/docs/real-time-stock-pricing-data
- Alpaca WebSocket stream: https://docs.alpaca.markets/us/docs/streaming-market-data
- Alpaca paper trading: https://docs.alpaca.markets/docs/paper-trading
- Alpaca order structures: https://docs.alpaca.markets/docs/orders-at-alpaca
- Alpaca create-order reference: https://docs.alpaca.markets/us/reference/postorder
- IBKR historical bars: https://interactivebrokers.github.io/tws-api/historical_bars.html
- IBKR Web API: https://www.interactivebrokers.com/campus/ibkr-api-page/web-api-trading/
- IBKR paper-account limitations: https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/
- TradeStation API: https://api.tradestation.com/docs/
- TradeStation API specification: https://api.tradestation.com/docs/specification/
- TradeStation SIM vs LIVE: https://api.tradestation.com/docs/fundamentals/sim-vs-live/
- Massive API documentation: https://massive.com/docs/
- Massive custom minute bars: https://massive.com/docs/rest/stocks/aggregates/custom-bars
- NYSE trading hours and calendars: https://www.nyse.com/markets/hours-calendars

## Definition of done

Do not declare the work complete until all applicable items below are true:

- The project installs from a clean environment.
- Database migrations run successfully.
- Fixture data can be loaded.
- The scanner produces deterministic results against fixtures.
- The alert engine emits and persists events.
- The UI displays live-style alerts and Top Lists.
- The backtest engine runs and produces a report.
- Paper intents and simulated fills work without any broker write call.
- The paper-only guard has automated tests.
- Reconnect, duplicate, stale-data, and correction behavior are tested.
- PowerShell scripts work or have been tested as far as the current environment permits.
- API documentation is generated.
- README setup instructions are complete.
- No secrets are committed.
- No live broker endpoint, live credential, order submission, or transaction action is present.
- `git diff`, tests, linting, type checks, and smoke tests have been reviewed.
- A final `STATUS.md` records what was implemented, what was tested, exact run commands, known limitations, and any genuine external blocker.

At the end, provide a concise completion report containing:

1. Files created or changed.
2. Commands executed.
3. Test results.
4. Local URLs and ports.
5. Paper-only safety verification.
6. Remaining blockers, if any.
7. Exact PowerShell commands only when user execution is genuinely required.

Continue until this definition of done is satisfied or until a genuine blocker requires user action.

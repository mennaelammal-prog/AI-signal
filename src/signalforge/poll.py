"""One-shot read-only scanner polling workflow."""

from __future__ import annotations

from typing import Any

from .connector import fetch_scanner_alerts
from .models import MarketContext, RankedSignal, RiskContext, StrategyStats
from .service import SignalForgeService


def poll_scanner_once(
    service: SignalForgeService,
    *,
    scanner_url: str = "http://127.0.0.1:8000",
    status: str | None = "triggered",
    limit: int = 100,
    market: MarketContext | None = None,
    risk_by_symbol: dict[str, RiskContext] | None = None,
) -> list[RankedSignal]:
    """Fetch current scanner alerts with GET and process them locally."""
    alerts = fetch_scanner_alerts(scanner_url, status=status, limit=limit)
    return service.process_alerts(alerts, market, risk_by_symbol)


def load_stats_records(records: list[dict[str, Any]]) -> list[StrategyStats]:
    """Validate imported point-in-time strategy evidence before storing it."""
    result = [StrategyStats(**record) for record in records]
    for item in result:
        item.validate()
    return result

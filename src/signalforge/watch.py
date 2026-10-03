"""Continuous read-only polling loop for local scanner alerts."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .connector import fetch_scanner_health
from .models import MarketContext, RiskContext
from .poll import poll_scanner_once
from .service import SignalForgeService


def watch_scanner(
    service: SignalForgeService,
    *,
    scanner_url: str = "http://127.0.0.1:8000",
    interval_seconds: float = 15.0,
    status: str | None = "triggered",
    limit: int = 100,
    market: MarketContext | None = None,
    risk_by_symbol: dict[str, RiskContext] | None = None,
    max_cycles: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    on_cycle: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Poll until interrupted or max_cycles is reached.

    Every cycle checks scanner health before reading alerts. A non-paper scanner refuses to poll.
    Duplicate scanner event IDs are harmless because SignalForge storage is immutable by event ID.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    cycles = 0
    processed = 0
    while max_cycles is None or cycles < max_cycles:
        health = fetch_scanner_health(scanner_url)
        results = poll_scanner_once(
            service,
            scanner_url=scanner_url,
            status=status,
            limit=limit,
            market=market,
            risk_by_symbol=risk_by_symbol,
        )
        cycles += 1
        processed += len(results)
        event = {
            "cycle": cycles,
            "fetched": len(results),
            "health": health,
            "summary": service.summary(),
            "paper_only": True,
            "broker_submission": False,
        }
        if on_cycle:
            on_cycle(event)
        if max_cycles is not None and cycles >= max_cycles:
            break
        sleep_fn(interval_seconds)
    return {"cycles": cycles, "processed": processed, **service.summary()}

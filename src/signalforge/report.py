"""Descriptive reports for hypothetical SignalForge outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def summarize_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Return descriptive metrics only; this is not a forecast or confidence estimate."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes:
        groups[str(outcome.get("strategy_id", "unknown"))].append(outcome)
    return {
        "paper_only": True,
        "hypothetical": True,
        "total_outcomes": len(outcomes),
        "overall": _metrics(outcomes),
        "by_strategy": {key: _metrics(value) for key, value in sorted(groups.items())},
        "by_exit_reason": _count_by(outcomes, "exit_reason"),
        "note": "Descriptive paper simulation metrics, not a prediction or live performance record.",
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl_pct"]) for row in rows]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_wins = sum(wins)
    gross_losses = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {
        "trade_count": len(pnls),
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 6) if pnls else None,
        "expectancy_pct": round(sum(pnls) / len(pnls), 6) if pnls else None,
        "profit_factor": round(gross_wins / gross_losses, 6) if gross_losses else None,
        "max_drawdown_pct": round(max_drawdown, 6),
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get(key, "unknown"))] += 1
    return dict(sorted(counts.items()))

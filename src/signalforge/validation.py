"""Validation helpers for paper-only SignalForge results.

These reports are designed to expose leakage and sensitivity. They do not establish profitability
or predict future returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    def as_dict(self) -> dict[str, str]:
        return {
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
        }


def build_walk_forward_windows(
    start: date,
    end: date,
    *,
    train_days: int = 20,
    test_days: int = 5,
    step_days: int | None = None,
) -> list[WalkForwardWindow]:
    if end <= start or train_days < 1 or test_days < 1:
        raise ValueError("end must be after start and window sizes must be positive")
    step = step_days or test_days
    if step < 1:
        raise ValueError("step_days must be positive")
    windows: list[WalkForwardWindow] = []
    cursor = start + timedelta(days=train_days)
    while cursor < end:
        test_end = min(cursor + timedelta(days=test_days), end)
        windows.append(WalkForwardWindow(start, cursor - timedelta(days=1), cursor, test_end - timedelta(days=1)))
        cursor += timedelta(days=step)
    return windows


def check_no_lookahead(signals: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> list[str]:
    """Return human-readable violations; an empty list is required for a clean report."""
    source_by_id = {str(signal["event_id"]): _parse(signal["source_timestamp"]) for signal in signals}
    errors: list[str] = []
    for outcome in outcomes:
        event_id = str(outcome["event_id"])
        source = source_by_id.get(event_id)
        if source is None:
            errors.append(f"outcome {event_id} has no matching source signal")
            continue
        entry = _parse(outcome["entry_timestamp"])
        exit_ts = _parse(outcome["exit_timestamp"])
        if entry <= source:
            errors.append(f"outcome {event_id} enters at or before the signal timestamp")
        if exit_ts < entry:
            errors.append(f"outcome {event_id} exits before entry")
    return errors


def walk_forward_report(
    signals: list[dict[str, Any]], outcomes: list[dict[str, Any]], windows: list[WalkForwardWindow]
) -> dict[str, Any]:
    errors = check_no_lookahead(signals, outcomes)
    outcome_by_id = {str(item["event_id"]): item for item in outcomes}
    signal_by_id = {str(item["event_id"]): item for item in signals}
    rows: list[dict[str, Any]] = []
    for window in windows:
        test_rows = []
        for event_id, outcome in outcome_by_id.items():
            signal = signal_by_id.get(event_id)
            if signal is None:
                continue
            signal_day = _parse(signal["source_timestamp"]).date()
            if window.test_start <= signal_day <= window.test_end:
                test_rows.append(outcome)
        rows.append({"window": window.as_dict(), "test": _metrics(test_rows), "test_signal_count": len(test_rows)})
    return {
        "paper_only": True,
        "hypothetical": True,
        "lookahead_errors": errors,
        "clean": not errors,
        "windows": rows,
        "note": "Walk-forward test summaries are historical paper simulations, not predictions.",
    }


def sensitivity_report(signals: list[dict[str, Any]], outcomes: list[dict[str, Any]], thresholds: list[float] | None = None) -> dict[str, Any]:
    """Compare descriptive outcome metrics at alternative score thresholds."""
    thresholds = thresholds or [0.0, 50.0, 60.0, 70.0, 80.0]
    outcome_by_id = {str(item["event_id"]): item for item in outcomes}
    rows = []
    for threshold in thresholds:
        selected = [outcome_by_id[str(signal["event_id"])] for signal in signals if float(signal.get("quality_score", 0)) >= threshold and str(signal["event_id"]) in outcome_by_id]
        rows.append({"minimum_score": threshold, "metrics": _metrics(selected)})
    return {
        "paper_only": True,
        "hypothetical": True,
        "thresholds": rows,
        "note": "Sensitivity comparison only; no threshold is a recommendation.",
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl_pct"]) for row in rows]
    return {
        "trade_count": len(pnls),
        "win_rate": round(sum(pnl > 0 for pnl in pnls) / len(pnls), 4) if pnls else None,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 6) if pnls else None,
    }


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)

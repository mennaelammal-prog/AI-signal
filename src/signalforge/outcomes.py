"""Paper-only outcome evaluator for ranked signals.

This module evaluates hypothetical entries against supplied historical bars. It never reads a broker
position and never submits an order. Bars must be timestamped after the signal event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from .models import RankedSignal

IntrabarPolicy = Literal["stop_first", "target_first", "reject_ambiguous"]


@dataclass(frozen=True, slots=True)
class OutcomeConfig:
    target_pct: float = 1.5
    stop_pct: float = 0.75
    max_hold_minutes: int = 90
    intrabar_policy: IntrabarPolicy = "stop_first"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0


@dataclass(frozen=True, slots=True)
class PaperOutcome:
    event_id: str
    symbol: str
    strategy_id: str
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    exit_reason: str
    entry_timestamp: str
    exit_timestamp: str
    bars_evaluated: int
    hypothetical: bool = True
    paper_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_pct": self.pnl_pct,
            "exit_reason": self.exit_reason,
            "entry_timestamp": self.entry_timestamp,
            "exit_timestamp": self.exit_timestamp,
            "bars_evaluated": self.bars_evaluated,
            "hypothetical": True,
            "paper_only": True,
        }


def evaluate_signal(
    signal: RankedSignal,
    bars: list[dict[str, Any]],
    config: OutcomeConfig | None = None,
) -> PaperOutcome:
    """Evaluate bars strictly after the signal timestamp.

    Bars are expected to contain `bar_ts`, `open`, `high`, `low`, and `close`. The first eligible
    bar's open is the modeled entry, avoiding the optimistic same-bar fill used by some backtests.
    """
    cfg = config or OutcomeConfig()
    if cfg.target_pct <= 0 or cfg.stop_pct <= 0 or cfg.max_hold_minutes <= 0:
        raise ValueError("target_pct, stop_pct, and max_hold_minutes must be positive")
    if cfg.intrabar_policy not in ("stop_first", "target_first", "reject_ambiguous"):
        raise ValueError("unknown intrabar policy")
    source = _parse(signal.candidate.source_timestamp)
    eligible = sorted((_bar(item) for item in bars), key=lambda item: item[0])
    eligible = [item for item in eligible if item[0] > source]
    if not eligible:
        raise ValueError("no future bars supplied after the signal timestamp")
    entry_ts, entry = eligible[0][0], eligible[0][1]["open"]
    if entry <= 0:
        raise ValueError("entry bar open must be positive")
    end = entry_ts + timedelta(minutes=cfg.max_hold_minutes)
    target = entry * (1 + cfg.target_pct / 100) if signal.candidate.direction == "long" else entry * (1 - cfg.target_pct / 100)
    stop = entry * (1 - cfg.stop_pct / 100) if signal.candidate.direction == "long" else entry * (1 + cfg.stop_pct / 100)
    for ts, bar in eligible:
        if ts > end:
            break
        hit_target = bar["high"] >= target if signal.candidate.direction == "long" else bar["low"] <= target
        hit_stop = bar["low"] <= stop if signal.candidate.direction == "long" else bar["high"] >= stop
        if hit_target and hit_stop:
            if cfg.intrabar_policy == "reject_ambiguous":
                return _outcome(signal, entry_ts, entry, entry_ts, entry, "ambiguous_bar_rejected", 1, cfg)
            reason = "target" if cfg.intrabar_policy == "target_first" else "stop"
            exit_price = target if reason == "target" else stop
            return _outcome(signal, entry_ts, entry, ts, exit_price, reason, _count(eligible, ts), cfg)
        if hit_target:
            return _outcome(signal, entry_ts, entry, ts, target, "target", _count(eligible, ts), cfg)
        if hit_stop:
            return _outcome(signal, entry_ts, entry, ts, stop, "stop", _count(eligible, ts), cfg)
    last_ts, last_bar = next((item for item in reversed(eligible) if item[0] <= end), eligible[-1])
    return _outcome(signal, entry_ts, entry, last_ts, last_bar["close"], "time_exit", _count(eligible, last_ts), cfg)


def _outcome(signal, entry_ts, entry, exit_ts, exit_price, reason, count, cfg):
    gross = (exit_price - entry) / entry * 100 if signal.candidate.direction == "long" else (entry - exit_price) / entry * 100
    pnl = gross - (cfg.commission_bps + cfg.slippage_bps) * 2 / 100
    return PaperOutcome(
        signal.candidate.event_id,
        signal.candidate.symbol,
        signal.candidate.strategy_id,
        signal.candidate.direction,
        round(entry, 8),
        round(exit_price, 8),
        round(pnl, 8),
        reason,
        entry_ts.isoformat().replace("+00:00", "Z"),
        exit_ts.isoformat().replace("+00:00", "Z"),
        count,
    )


def _bar(raw):
    ts = _parse(str(raw["bar_ts"]))
    values = {key: float(raw[key]) for key in ("open", "high", "low", "close")}
    if min(values.values()) <= 0 or values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
        raise ValueError("invalid OHLC bar")
    return ts, values


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def _count(items, ts):
    return sum(item[0] <= ts for item in items)

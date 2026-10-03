"""Versioned, paper-only SignalForge domain contracts.

The scanner remains the source of candidate events. SignalForge ranks and explains those events;
it never creates or submits a broker order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["long", "short"]
SignalStatus = Literal[
    "candidate",
    "qualified",
    "ranked",
    "published",
    "rejected_spread",
    "rejected_liquidity",
    "rejected_stale_data",
    "rejected_market_regime",
    "rejected_correlation",
    "rejected_daily_risk",
    "rejected_strategy_quality",
]


class SignalValidationError(ValueError):
    """Raised when an input is unsafe or incomplete for SignalForge."""


@dataclass(frozen=True, slots=True)
class CandidateSignal:
    event_id: str
    symbol: str
    strategy_id: str
    strategy_version: int
    direction: Direction
    event_type: str
    source_timestamp: str
    detected_timestamp: str
    session: str
    trigger_price: float
    bid: float | None
    ask: float | None
    spread_bps: float | None
    feature_snapshot: dict[str, Any]
    filter_snapshot: dict[str, Any]
    data_provider: str
    data_feed: str
    paper_only: bool = True
    hypothetical: bool = True

    @classmethod
    def from_scanner_alert(cls, alert: dict[str, Any]) -> CandidateSignal:
        """Adapt the scanalert AlertEvent JSON contract without importing scanalert."""
        required = (
            "event_id",
            "symbol",
            "strategy_id",
            "strategy_version",
            "direction",
            "event_type",
            "source_timestamp",
            "detected_timestamp",
            "session",
            "trigger_price",
        )
        missing = [key for key in required if key not in alert]
        if missing:
            raise SignalValidationError(f"scanner alert missing required fields: {', '.join(missing)}")
        if alert.get("paper_only") is not True or alert.get("hypothetical") is not True:
            raise SignalValidationError("SignalForge accepts paper-only hypothetical scanner events only")
        price = alert.get("trigger_price")
        if not isinstance(price, (int, float)) or price <= 0:
            raise SignalValidationError("trigger_price must be a positive number")
        direction = alert["direction"]
        if direction not in ("long", "short"):
            raise SignalValidationError("direction must be long or short")
        symbol = str(alert["symbol"]).strip().upper()
        if not symbol:
            raise SignalValidationError("symbol cannot be empty")
        return cls(
            event_id=str(alert["event_id"]),
            symbol=symbol,
            strategy_id=str(alert["strategy_id"]),
            strategy_version=int(alert["strategy_version"]),
            direction=direction,
            event_type=str(alert["event_type"]),
            source_timestamp=str(alert["source_timestamp"]),
            detected_timestamp=str(alert["detected_timestamp"]),
            session=str(alert["session"]),
            trigger_price=float(price),
            bid=_number(alert.get("bid")),
            ask=_number(alert.get("ask")),
            spread_bps=_number(alert.get("spread_bps")),
            feature_snapshot=dict(alert.get("feature_snapshot") or {}),
            filter_snapshot=dict(alert.get("filter_snapshot") or {}),
            data_provider=str(alert.get("data_provider") or ""),
            data_feed=str(alert.get("data_feed") or ""),
        )


@dataclass(frozen=True, slots=True)
class StrategyStats:
    """Point-in-time strategy evidence supplied by the evaluation service."""

    strategy_id: str
    strategy_version: int
    sample_size: int
    expectancy_r: float
    win_rate: float
    profit_factor: float | None
    max_drawdown_r: float
    out_of_sample_expectancy_r: float | None = None
    recent_expectancy_r: float | None = None
    regime_expectancy_r: dict[str, float] = field(default_factory=dict)
    time_bucket_expectancy: dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.sample_size < 0:
            raise SignalValidationError("sample_size cannot be negative")
        if not 0 <= self.win_rate <= 1:
            raise SignalValidationError("win_rate must be between 0 and 1")
        if self.max_drawdown_r < 0:
            raise SignalValidationError("max_drawdown_r cannot be negative")


@dataclass(frozen=True, slots=True)
class MarketContext:
    regime: str = "unknown"
    market_breadth: float | None = None
    index_return_pct: float | None = None
    sector_return_pct: float | None = None
    volatility_pct: float | None = None
    minutes_since_open: int | None = None
    minutes_to_close: int | None = None


@dataclass(frozen=True, slots=True)
class RiskContext:
    max_spread_bps: float = 60.0
    min_dollar_volume: float = 250_000.0
    max_signal_correlation: float = 0.85
    current_correlation: float | None = None
    data_age_seconds: float | None = None
    stale_after_seconds: float = 15.0
    liquidity_dollar_volume: float | None = None
    daily_risk_locked: bool = False


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    strategy: float
    feature_alignment: float
    liquidity: float
    regime: float
    timing: float
    spread_penalty: float
    volatility_penalty: float
    correlation_penalty: float
    drawdown_penalty: float
    stale_penalty: float

    @property
    def total(self) -> float:
        raw = (
            self.strategy
            + self.feature_alignment
            + self.liquidity
            + self.regime
            + self.timing
            - self.spread_penalty
            - self.volatility_penalty
            - self.correlation_penalty
            - self.drawdown_penalty
            - self.stale_penalty
        )
        return round(max(0.0, min(100.0, raw)), 4)

    def as_dict(self) -> dict[str, float]:
        return {
            "strategy": self.strategy,
            "feature_alignment": self.feature_alignment,
            "liquidity": self.liquidity,
            "regime": self.regime,
            "timing": self.timing,
            "spread_penalty": self.spread_penalty,
            "volatility_penalty": self.volatility_penalty,
            "correlation_penalty": self.correlation_penalty,
            "drawdown_penalty": self.drawdown_penalty,
            "stale_penalty": self.stale_penalty,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class RankedSignal:
    candidate: CandidateSignal
    score: ScoreBreakdown
    status: SignalStatus
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    model_version: str
    feature_version: str
    paper_only: bool = True
    hypothetical: bool = True

    @property
    def quality_score(self) -> float:
        return self.score.total

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.candidate.event_id,
            "symbol": self.candidate.symbol,
            "strategy_id": self.candidate.strategy_id,
            "strategy_version": self.candidate.strategy_version,
            "direction": self.candidate.direction,
            "event_type": self.candidate.event_type,
            "source_timestamp": self.candidate.source_timestamp,
            "trigger_price": self.candidate.trigger_price,
            "quality_score": self.quality_score,
            "score_components": self.score.as_dict(),
            "status": self.status,
            "reasons": list(self.reasons),
            "risks": list(self.risks),
            "invalidation_conditions": list(self.invalidation_conditions),
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "paper_only": True,
            "hypothetical": True,
            "label": "HYPOTHETICAL SIGNAL - PAPER ONLY - NOT AN ORDER",
        }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise SignalValidationError(f"expected numeric value, got {type(value).__name__}")

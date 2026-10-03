"""Read-only ingestion boundary between scanalert alerts and SignalForge ranking."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import CandidateSignal, MarketContext, RankedSignal, RiskContext
from .outcomes import OutcomeConfig, PaperOutcome, evaluate_signal
from .scoring import SignalForgeEngine
from .store import SignalStore


class SignalForgeService:
    """Process scanner alert payloads into ranked paper-only signals.

    This service has no broker dependency and no order-writing method by design.
    """

    def __init__(self, store: SignalStore, engine: SignalForgeEngine | None = None):
        self.store = store
        self.engine = engine or SignalForgeEngine()

    def process_alert(
        self,
        alert: dict[str, Any],
        market: MarketContext | None = None,
        risk: RiskContext | None = None,
    ) -> RankedSignal:
        candidate = CandidateSignal.from_scanner_alert(alert)
        stats = self.store.get_strategy_stats(candidate.strategy_id, candidate.strategy_version)
        if stats is None:
            result = self.engine.rank_many([candidate], {})[0]
        else:
            result = self.engine.rank(candidate, stats, market, risk)
        self.store.save_ranked_signal(result)
        return result

    def process_alerts(
        self,
        alerts: Iterable[dict[str, Any]],
        market: MarketContext | None = None,
        risk_by_symbol: dict[str, RiskContext] | None = None,
    ) -> list[RankedSignal]:
        candidates = [CandidateSignal.from_scanner_alert(alert) for alert in alerts]
        stats = {
            (candidate.strategy_id, candidate.strategy_version): self.store.get_strategy_stats(
                candidate.strategy_id, candidate.strategy_version
            )
            for candidate in candidates
        }
        results = self.engine.rank_many(
            candidates,
            {key: value for key, value in stats.items() if value is not None},
            market,
            risk_by_symbol,
        )
        for result in results:
            self.store.save_ranked_signal(result)
        return results

    def summary(self) -> dict[str, Any]:
        rows = self.store.list_signals(limit=1_000_000)
        outcomes = self.store.list_outcomes(limit=1_000_000)
        return {
            "signals": len(rows),
            "published": sum(row["status"] == "published" for row in rows),
            "qualified": sum(row["status"] == "qualified" for row in rows),
            "rejected": sum(row["status"].startswith("rejected_") for row in rows),
            "outcomes": len(outcomes),
            "outcome_win_rate": (
                round(sum(item["pnl_pct"] > 0 for item in outcomes) / len(outcomes), 4) if outcomes else None
            ),
            "paper_only": True,
            "broker_submission": False,
        }

    def evaluate_outcome(
        self, result: RankedSignal, bars: list[dict[str, Any]], config: OutcomeConfig | None = None
    ) -> PaperOutcome:
        if not result.paper_only or not result.hypothetical:
            raise ValueError("only paper-only hypothetical signals can be evaluated")
        outcome = evaluate_signal(result, bars, config)
        self.store.save_outcome(outcome)
        return outcome

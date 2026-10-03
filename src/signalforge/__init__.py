"""SignalForge AI: explainable paper-only signal ranking."""

from .connector import ScannerConnectorError, fetch_scanner_alerts, fetch_scanner_health
from .models import CandidateSignal, MarketContext, RankedSignal, RiskContext, StrategyStats
from .outcomes import OutcomeConfig, PaperOutcome, evaluate_signal
from .poll import load_stats_records, poll_scanner_once
from .report import summarize_outcomes
from .scoring import ScoringConfig, SignalForgeEngine
from .service import SignalForgeService
from .store import SignalStore
from .validation import (
    build_walk_forward_windows,
    check_no_lookahead,
    sensitivity_report,
    walk_forward_report,
)
from .watch import watch_scanner

__all__ = [
    "CandidateSignal",
    "MarketContext",
    "RankedSignal",
    "RiskContext",
    "StrategyStats",
    "ScoringConfig",
    "SignalForgeEngine",
    "SignalForgeService",
    "SignalStore",
    "ScannerConnectorError",
    "fetch_scanner_alerts",
    "fetch_scanner_health",
    "OutcomeConfig",
    "PaperOutcome",
    "evaluate_signal",
    "load_stats_records",
    "poll_scanner_once",
    "summarize_outcomes",
    "build_walk_forward_windows",
    "check_no_lookahead",
    "sensitivity_report",
    "walk_forward_report",
    "watch_scanner",
]

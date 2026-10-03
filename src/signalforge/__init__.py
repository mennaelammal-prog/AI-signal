"""SignalForge AI: explainable paper-only signal ranking."""

from .connector import ScannerConnectorError, fetch_scanner_alerts
from .models import CandidateSignal, MarketContext, RankedSignal, RiskContext, StrategyStats
from .outcomes import OutcomeConfig, PaperOutcome, evaluate_signal
from .scoring import ScoringConfig, SignalForgeEngine
from .service import SignalForgeService
from .store import SignalStore

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
    "OutcomeConfig",
    "PaperOutcome",
    "evaluate_signal",
]

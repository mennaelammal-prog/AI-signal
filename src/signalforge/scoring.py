"""Explainable deterministic scoring for paper-only candidate signals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import CandidateSignal, MarketContext, RankedSignal, RiskContext, ScoreBreakdown, StrategyStats


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    model_version: str = "signalforge-baseline-v1"
    feature_version: str = "features-v1"
    minimum_sample_size: int = 30
    publish_threshold: float = 55.0


class SignalForgeEngine:
    """Rank scanner candidates without making a prediction or sending an order."""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or ScoringConfig()

    def rank(
        self,
        candidate: CandidateSignal,
        stats: StrategyStats,
        market: MarketContext | None = None,
        risk: RiskContext | None = None,
    ) -> RankedSignal:
        stats.validate()
        market = market or MarketContext()
        risk = risk or RiskContext()
        reasons: list[str] = []
        risks: list[str] = []
        invalidation: list[str] = []

        gate = self._gate(candidate, stats, market, risk)
        if gate:
            reasons.append("Candidate was received from a paper-only deterministic scanner event.")
            return RankedSignal(
                candidate,
                ScoreBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0, gate[1]),
                gate[0],
                tuple(reasons),
                tuple(gate[2]),
                ("Data must remain fresh and the rejection condition must clear.",),
                self.config.model_version,
                self.config.feature_version,
            )

        strategy = _clamp(25 + stats.expectancy_r * 12 + (stats.out_of_sample_expectancy_r or 0) * 8, 0, 35)
        feature = self._feature_alignment(candidate, reasons, risks)
        liquidity = self._liquidity(candidate, risk, reasons, risks)
        regime = self._regime(candidate, stats, market, reasons, risks)
        timing = self._timing(market, stats, reasons)
        spread_penalty = self._spread_penalty(candidate, risk, risks)
        volatility_penalty = self._volatility_penalty(market, risks)
        correlation_penalty = self._correlation_penalty(risk, risks)
        drawdown_penalty = _clamp(stats.max_drawdown_r * 2, 0, 12)
        stale_penalty = self._stale_penalty(risk, risks)

        if drawdown_penalty:
            risks.append(f"Strategy drawdown penalty: {stats.max_drawdown_r:.2f}R historical maximum.")
        if stats.sample_size < self.config.minimum_sample_size:
            risks.append(f"Small historical sample: {stats.sample_size} trades; score is not statistically mature.")
        if stats.profit_factor is not None:
            reasons.append(f"Historical profit factor: {stats.profit_factor:.2f}.")

        score = ScoreBreakdown(
            strategy,
            feature,
            liquidity,
            regime,
            timing,
            spread_penalty,
            volatility_penalty,
            correlation_penalty,
            drawdown_penalty,
            stale_penalty,
        )
        status = "published" if score.total >= self.config.publish_threshold else "qualified"
        invalidation.extend(self._invalidation(candidate, market, risk))
        return RankedSignal(
            candidate,
            score,
            status,
            tuple(_unique(reasons)),
            tuple(_unique(risks)),
            tuple(_unique(invalidation)),
            self.config.model_version,
            self.config.feature_version,
        )

    def rank_many(
        self,
        candidates: Iterable[CandidateSignal],
        stats_by_strategy: dict[tuple[str, int], StrategyStats],
        market: MarketContext | None = None,
        risk_by_symbol: dict[str, RiskContext] | None = None,
    ) -> list[RankedSignal]:
        results: list[RankedSignal] = []
        for candidate in candidates:
            stats = stats_by_strategy.get((candidate.strategy_id, candidate.strategy_version))
            if stats is None:
                results.append(self._rejected_missing_stats(candidate))
                continue
            results.append(self.rank(candidate, stats, market, (risk_by_symbol or {}).get(candidate.symbol)))
        return sorted(results, key=lambda x: (-x.quality_score, x.candidate.symbol, x.candidate.event_id))

    def _gate(self, c: CandidateSignal, s: StrategyStats, m: MarketContext, r: RiskContext):
        if c.spread_bps is not None and c.spread_bps > r.max_spread_bps:
            return "rejected_spread", 20.0, [f"Spread {c.spread_bps:.1f} bps exceeds {r.max_spread_bps:.1f} bps limit."]
        if r.liquidity_dollar_volume is not None and r.liquidity_dollar_volume < r.min_dollar_volume:
            return "rejected_liquidity", 15.0, [f"Dollar volume {r.liquidity_dollar_volume:.0f} is below the configured minimum."]
        if r.data_age_seconds is not None and r.data_age_seconds > r.stale_after_seconds:
            return "rejected_stale_data", 20.0, [f"Data age {r.data_age_seconds:.1f}s exceeds {r.stale_after_seconds:.1f}s."]
        if r.current_correlation is not None and r.current_correlation > r.max_signal_correlation:
            return "rejected_correlation", 10.0, [f"Correlation {r.current_correlation:.2f} exceeds the configured limit."]
        if r.daily_risk_locked:
            return "rejected_daily_risk", 10.0, ["Daily paper-risk lock is active."]
        if s.sample_size < 1:
            return "rejected_strategy_quality", 10.0, ["No historical strategy evidence is available."]
        return None

    def _rejected_missing_stats(self, c: CandidateSignal) -> RankedSignal:
        return RankedSignal(
            c,
            ScoreBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            "rejected_strategy_quality",
            (),
            ("No version-matched strategy evaluation was supplied.",),
            ("Provide point-in-time evaluation evidence before publishing.",),
            self.config.model_version,
            self.config.feature_version,
        )

    def _feature_alignment(self, c, reasons, risks):
        fs = c.feature_snapshot
        score = 8.0
        if _truth(fs.get("above_vwap")) or _positive(fs.get("vwap_dist_pct")):
            score += 5
            reasons.append("Price is above VWAP in the candidate feature snapshot.")
        if _at_least(fs.get("rvol"), 1.5):
            score += 5
            reasons.append(f"Relative volume is elevated at {float(fs['rvol']):.2f}x.")
        if _truth(fs.get("new_high")) or _truth(fs.get("orb_breakout_up")):
            score += 5
            reasons.append("The event is supported by a new-high or opening-range breakout feature.")
        if _negative(fs.get("vwap_dist_pct")):
            risks.append("Price is below VWAP in the candidate feature snapshot.")
        return _clamp(score, 0, 20)

    def _liquidity(self, c, r, reasons, risks):
        dollar_volume = r.liquidity_dollar_volume
        if dollar_volume is None:
            dollar_volume = _number(c.feature_snapshot.get("dollar_volume"))
        if dollar_volume is None:
            risks.append("Liquidity evidence is missing; no liquidity bonus awarded.")
            return 3.0
        score = _clamp(dollar_volume / max(r.min_dollar_volume, 1) * 5, 0, 10)
        if score >= 5:
            reasons.append(f"Dollar volume supports liquidity ({dollar_volume:,.0f}).")
        return score

    def _regime(self, c, s, m, reasons, risks):
        value = s.regime_expectancy_r.get(m.regime)
        if value is None:
            risks.append(f"No strategy evidence is available for market regime '{m.regime}'.")
            return 4.0
        reasons.append(f"Strategy expectancy in regime '{m.regime}': {value:.2f}R.")
        return _clamp(8 + value * 5, 0, 15)

    def _timing(self, m, s, reasons):
        if m.minutes_since_open is None:
            return 4.0
        bucket = _time_bucket(m.minutes_since_open)
        value = s.time_bucket_expectancy.get(bucket)
        if value is None:
            return 4.0
        reasons.append(f"Time bucket '{bucket}' expectancy: {value:.2f}R.")
        return _clamp(5 + value * 3, 0, 10)

    def _spread_penalty(self, c, r, risks):
        if c.spread_bps is None:
            risks.append("Spread is unavailable; spread penalty cannot be fully evaluated.")
            return 2.0
        penalty = _clamp((c.spread_bps / max(r.max_spread_bps, 1)) * 8, 0, 12)
        if penalty >= 5:
            risks.append(f"Spread cost is elevated at {c.spread_bps:.1f} bps.")
        return penalty

    def _volatility_penalty(self, m, risks):
        if m.volatility_pct is None:
            return 0.0
        penalty = _clamp(max(0.0, m.volatility_pct - 8) * 0.5, 0, 8)
        if penalty:
            risks.append(f"Volatility penalty applied at {m.volatility_pct:.2f}%.")
        return penalty

    def _correlation_penalty(self, r, risks):
        if r.current_correlation is None:
            return 0.0
        penalty = _clamp(max(0.0, r.current_correlation - 0.5) * 10, 0, 8)
        if penalty:
            risks.append(f"Existing-signal correlation penalty applied at {r.current_correlation:.2f}.")
        return penalty

    def _stale_penalty(self, r, risks):
        if r.data_age_seconds is None:
            return 0.0
        penalty = _clamp(max(0.0, r.data_age_seconds / max(r.stale_after_seconds, 1) - 0.5) * 4, 0, 8)
        if penalty:
            risks.append(f"Data freshness penalty applied at {r.data_age_seconds:.1f}s age.")
        return penalty

    def _invalidation(self, c, m, r):
        result = ["Data becomes stale beyond the configured freshness limit."]
        if c.direction == "long":
            result.append("Price loses the event level or the configured VWAP/structure condition.")
        else:
            result.append("Price reclaims the event level or the configured VWAP/structure condition.")
        if m.minutes_to_close is not None:
            result.append("Session closes before the modeled exit rules complete.")
        if c.spread_bps is not None:
            result.append("Spread exceeds the configured maximum before a paper fill.")
        return result


def _clamp(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 4)


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _positive(value):
    return isinstance(value, (int, float)) and value > 0


def _negative(value):
    return isinstance(value, (int, float)) and value < 0


def _at_least(value, threshold):
    return isinstance(value, (int, float)) and value >= threshold


def _truth(value):
    return value is True


def _time_bucket(minutes: int) -> str:
    if minutes < 30:
        return "open"
    if minutes < 120:
        return "morning"
    if minutes < 300:
        return "midday"
    return "close"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))

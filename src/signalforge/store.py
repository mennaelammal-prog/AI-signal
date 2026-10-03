"""Small SQLite store for paper-only SignalForge results.

The store is intentionally independent of the scanner database. It accepts serialized scanner alerts
and preserves the exact strategy, feature, model, score, and explanation versions used for each result.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import RankedSignal, StrategyStats
from .outcomes import PaperOutcome


class SignalStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self.db.close()

    def _migrate(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_evaluations (
                strategy_id TEXT NOT NULL,
                strategy_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (strategy_id, strategy_version)
            );
            CREATE TABLE IF NOT EXISTS ranked_signals (
                event_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version INTEGER NOT NULL,
                source_timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                quality_score REAL NOT NULL,
                model_version TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ranked_signals_symbol ON ranked_signals(symbol);
            CREATE INDEX IF NOT EXISTS idx_ranked_signals_status ON ranked_signals(status);
            CREATE TABLE IF NOT EXISTS paper_outcomes (
                event_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                exit_reason TEXT NOT NULL,
                pnl_pct REAL NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES ranked_signals(event_id)
            );
            """
        )
        self.db.commit()

    def save_strategy_stats(self, stats: StrategyStats) -> None:
        stats.validate()
        payload = {
            "strategy_id": stats.strategy_id,
            "strategy_version": stats.strategy_version,
            "sample_size": stats.sample_size,
            "expectancy_r": stats.expectancy_r,
            "win_rate": stats.win_rate,
            "profit_factor": stats.profit_factor,
            "max_drawdown_r": stats.max_drawdown_r,
            "out_of_sample_expectancy_r": stats.out_of_sample_expectancy_r,
            "recent_expectancy_r": stats.recent_expectancy_r,
            "regime_expectancy_r": stats.regime_expectancy_r,
            "time_bucket_expectancy": stats.time_bucket_expectancy,
        }
        self.db.execute(
            "INSERT INTO strategy_evaluations(strategy_id,strategy_version,payload_json) VALUES(?,?,?) "
            "ON CONFLICT(strategy_id,strategy_version) DO UPDATE SET payload_json=excluded.payload_json",
            (stats.strategy_id, stats.strategy_version, json.dumps(payload, sort_keys=True)),
        )
        self.db.commit()

    def get_strategy_stats(self, strategy_id: str, strategy_version: int) -> StrategyStats | None:
        row = self.db.execute(
            "SELECT payload_json FROM strategy_evaluations WHERE strategy_id=? AND strategy_version=?",
            (strategy_id, strategy_version),
        ).fetchone()
        if row is None:
            return None
        return StrategyStats(**json.loads(row["payload_json"]))

    def save_ranked_signal(self, result: RankedSignal) -> bool:
        """Persist once by event_id; return False for a duplicate immutable event."""
        payload = json.dumps(result.as_dict(), sort_keys=True)
        cur = self.db.execute(
            "INSERT OR IGNORE INTO ranked_signals(event_id,symbol,strategy_id,strategy_version,source_timestamp,status,"
            "quality_score,model_version,feature_version,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                result.candidate.event_id,
                result.candidate.symbol,
                result.candidate.strategy_id,
                result.candidate.strategy_version,
                result.candidate.source_timestamp,
                result.status,
                result.quality_score,
                result.model_version,
                result.feature_version,
                payload,
            ),
        )
        self.db.commit()
        return cur.rowcount == 1

    def get_signal(self, event_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload_json FROM ranked_signals WHERE event_id=?", (event_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_signals(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if status:
            rows = self.db.execute(
                "SELECT payload_json FROM ranked_signals WHERE status=? ORDER BY quality_score DESC, event_id LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT payload_json FROM ranked_signals ORDER BY quality_score DESC, event_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def count_signals(self) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM ranked_signals").fetchone()
        return int(row["n"])

    def save_outcome(self, outcome: PaperOutcome) -> bool:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO paper_outcomes(event_id,symbol,exit_reason,pnl_pct,payload_json) VALUES(?,?,?,?,?)",
            (
                outcome.event_id,
                outcome.symbol,
                outcome.exit_reason,
                outcome.pnl_pct,
                json.dumps(outcome.as_dict(), sort_keys=True),
            ),
        )
        self.db.commit()
        return cur.rowcount == 1

    def get_outcome(self, event_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload_json FROM paper_outcomes WHERE event_id=?", (event_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_outcomes(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT payload_json FROM paper_outcomes ORDER BY created_at DESC, event_id LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def export_json(self) -> list[dict[str, Any]]:
        return self.list_signals(limit=1_000_000)

    def save_many_stats(self, stats: Iterable[StrategyStats]) -> None:
        for item in stats:
            self.save_strategy_stats(item)

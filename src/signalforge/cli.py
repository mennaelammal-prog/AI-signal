"""Command-line entry point for local paper-only SignalForge processing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .models import MarketContext, StrategyStats
from .service import SignalForgeService
from .store import SignalStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signalforge", description="Paper-only SignalForge signal ranking")
    sub = parser.add_subparsers(dest="command", required=True)
    rank = sub.add_parser("rank", help="rank scanner alerts from JSON")
    rank.add_argument("--alerts", required=True, type=Path, help="JSON array or JSON-lines scanner alerts")
    rank.add_argument("--stats", required=True, type=Path, help="JSON array of strategy evaluation records")
    rank.add_argument("--db", default=":memory:", help="SQLite path, default is in-memory")
    rank.add_argument("--market", type=Path, help="optional JSON market context")
    rank.add_argument("--output", type=Path, help="optional JSON output path")
    rank.add_argument("--min-score", type=float, default=None, help="optional display threshold")
    args = parser.parse_args(argv)
    if args.command == "rank":
        return _rank(args)
    return 2


def _rank(args: argparse.Namespace) -> int:
    store = SignalStore(args.db)
    try:
        raw_stats = _load_json(args.stats)
        if not isinstance(raw_stats, list):
            raise ValueError("--stats must contain a JSON array")
        store.save_many_stats(StrategyStats(**item) for item in raw_stats)
        alerts = _load_alerts(args.alerts)
        market = MarketContext(**_load_json(args.market)) if args.market else MarketContext()
        service = SignalForgeService(store)
        results = service.process_alerts(alerts, market)
        payload: dict[str, Any] = {
            "summary": service.summary(),
            "signals": [
                result.as_dict()
                for result in results
                if args.min_score is None or result.quality_score >= args.min_score
            ],
        }
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"signalforge: {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_alerts(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        value = json.loads(text)
        if not isinstance(value, list):
            raise ValueError("--alerts JSON must be an array or JSON-lines")
        return value
    return [json.loads(line) for line in text.splitlines() if line.strip()]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

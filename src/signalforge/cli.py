"""Command-line entry point for local paper-only SignalForge processing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .models import MarketContext, StrategyStats
from .poll import load_stats_records, poll_scanner_once
from .report import summarize_outcomes
from .service import SignalForgeService
from .store import SignalStore
from .validation import build_walk_forward_windows, sensitivity_report, walk_forward_report
from .watch import watch_scanner
from .web import serve_dashboard


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
    serve = sub.add_parser("serve", help="serve the read-only local dashboard")
    serve.add_argument("--db", required=True, help="SQLite path created by rank processing")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    report = sub.add_parser("report", help="report descriptive paper outcomes")
    report.add_argument("--db", required=True, help="SQLite path")
    validate = sub.add_parser("validate", help="run leakage, walk-forward, and sensitivity checks")
    validate.add_argument("--signals", required=True, type=Path, help="ranked signal JSON array")
    validate.add_argument("--outcomes", required=True, type=Path, help="paper outcome JSON array")
    validate.add_argument("--start", required=True, help="window start date YYYY-MM-DD")
    validate.add_argument("--end", required=True, help="window end date YYYY-MM-DD")
    validate.add_argument("--train-days", type=int, default=20)
    validate.add_argument("--test-days", type=int, default=5)
    poll = sub.add_parser("poll", help="fetch scanner alerts once and rank them")
    poll.add_argument("--scanner-url", default="http://127.0.0.1:8000")
    poll.add_argument("--stats", required=True, type=Path)
    poll.add_argument("--db", required=True)
    poll.add_argument("--status", default="triggered")
    poll.add_argument("--limit", type=int, default=100)
    watch = sub.add_parser("watch", help="continuously poll scanner alerts in paper mode")
    watch.add_argument("--scanner-url", default="http://127.0.0.1:8000")
    watch.add_argument("--stats", required=True, type=Path)
    watch.add_argument("--db", required=True)
    watch.add_argument("--status", default="triggered")
    watch.add_argument("--limit", type=int, default=100)
    watch.add_argument("--interval", type=float, default=15.0)
    watch.add_argument("--cycles", type=int, default=None, help="stop after N cycles; omit for continuous mode")
    args = parser.parse_args(argv)
    if args.command == "rank":
        return _rank(args)
    if args.command == "serve":
        serve_dashboard(args.db, args.host, args.port)
        return 0
    if args.command == "report":
        store = SignalStore(args.db)
        try:
            print(json.dumps(summarize_outcomes(store.list_outcomes(limit=1_000_000)), indent=2, sort_keys=True))
            return 0
        finally:
            store.close()
    if args.command == "validate":
        from datetime import date

        signals = _load_json(args.signals)
        outcomes = _load_json(args.outcomes)
        windows = build_walk_forward_windows(
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
            train_days=args.train_days,
            test_days=args.test_days,
        )
        payload = {
            "walk_forward": walk_forward_report(signals, outcomes, windows),
            "sensitivity": sensitivity_report(signals, outcomes),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "poll":
        store = SignalStore(args.db)
        try:
            records = _load_json(args.stats)
            store.save_many_stats(load_stats_records(records))
            results = poll_scanner_once(
                SignalForgeService(store),
                scanner_url=args.scanner_url,
                status=args.status,
                limit=args.limit,
            )
            print(json.dumps({"summary": SignalForgeService(store).summary(), "signals": [x.as_dict() for x in results]}, indent=2, sort_keys=True))
            return 0
        finally:
            store.close()
    if args.command == "watch":
        store = SignalStore(args.db)
        try:
            records = _load_json(args.stats)
            store.save_many_stats(load_stats_records(records))
            service = SignalForgeService(store)
            result = watch_scanner(
                service,
                scanner_url=args.scanner_url,
                interval_seconds=args.interval,
                status=args.status,
                limit=args.limit,
                max_cycles=args.cycles,
                on_cycle=lambda event: print(json.dumps(event, sort_keys=True), flush=True),
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        except KeyboardInterrupt:
            print(json.dumps({"stopped": "keyboard_interrupt", "paper_only": True}, sort_keys=True))
            return 0
        finally:
            store.close()
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

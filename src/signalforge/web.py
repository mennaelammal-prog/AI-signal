"""Read-only local dashboard for SignalForge paper results."""

from __future__ import annotations

import json
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

from .store import SignalStore


def build_dashboard_html(summary: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    rows = []
    for signal in signals:
        reasons = "<br>".join(escape(str(x)) for x in signal.get("reasons", [])) or "—"
        risks = "<br>".join(escape(str(x)) for x in signal.get("risks", [])) or "—"
        rows.append(
            "<tr>"
            f"<td>{escape(str(signal.get('symbol', '')))}</td>"
            f"<td>{escape(str(signal.get('direction', '')))}</td>"
            f"<td>{escape(str(signal.get('strategy_id', '')))} v{escape(str(signal.get('strategy_version', '')))}</td>"
            f"<td>{float(signal.get('quality_score', 0)):.2f}</td>"
            f"<td>{escape(str(signal.get('status', '')))}</td>"
            f"<td>{reasons}</td><td>{risks}</td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="7">No signals stored.</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SignalForge AI — Paper Dashboard</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f5f7fb;color:#172033}} .banner{{background:#172033;color:#fff;padding:1rem;border-radius:8px}}
.cards{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}} .card{{background:#fff;border:1px solid #d8deea;border-radius:8px;padding:1rem;min-width:130px}}
table{{background:#fff;border-collapse:collapse;width:100%;font-size:.9rem}}th,td{{border:1px solid #d8deea;padding:.6rem;text-align:left;vertical-align:top}}th{{background:#e9eef7}} .published{{color:#087443;font-weight:700}} .rejected_strategy_quality,.rejected_stale_data,.rejected_spread{{color:#9b2c2c;font-weight:700}}
small{{color:#5a6578}}
</style></head><body>
<div class="banner"><h1>SignalForge AI</h1><strong>PAPER ONLY — HYPOTHETICAL SIGNALS — NOT ORDERS</strong><br><small>Read-only local review dashboard. No broker connection or order endpoint.</small></div>
<div class="cards"><div class="card"><b>Signals</b><br>{summary.get('signals', 0)}</div><div class="card"><b>Published</b><br>{summary.get('published', 0)}</div><div class="card"><b>Qualified</b><br>{summary.get('qualified', 0)}</div><div class="card"><b>Rejected</b><br>{summary.get('rejected', 0)}</div><div class="card"><b>Outcomes</b><br>{summary.get('outcomes', 0)}</div><div class="card"><b>Paper win rate</b><br>{summary.get('outcome_win_rate') if summary.get('outcome_win_rate') is not None else '—'}</div></div>
<h2>Ranked signals</h2><table><thead><tr><th>Symbol</th><th>Direction</th><th>Strategy</th><th>Quality score</th><th>Status</th><th>Reasons</th><th>Risks</th></tr></thead><tbody>{body}</tbody></table>
<p><small>API: <a href="/api/summary">/api/summary</a> · <a href="/api/signals">/api/signals</a></small></p>
</body></html>"""


def serve_dashboard(db_path: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    store = SignalStore(db_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            summary = _safe_summary(store)
            if path == "/api/summary":
                _json(self, summary)
            elif path == "/api/signals":
                _json(self, store.list_signals(limit=1000))
            elif path == "/":
                _html(self, build_dashboard_html(summary, store.list_signals(limit=1000)))
            else:
                self.send_error(404, "not found")

        def log_message(self, _format, *_args):
            return

    # The dashboard is a local read-only review surface. A single-threaded server keeps the
    # deliberately simple SQLite connection thread-safe without adding a write-capable API.
    server = HTTPServer((host, port), Handler)
    try:
        print(f"SignalForge paper dashboard: http://{host}:{port}/")
        server.serve_forever()
    finally:
        server.server_close()
        store.close()


def _safe_summary(store: SignalStore) -> dict[str, Any]:
    rows = store.list_signals(limit=1_000_000)
    outcomes = store.list_outcomes(limit=1_000_000)
    return {
        "signals": len(rows),
        "published": sum(row["status"] == "published" for row in rows),
        "qualified": sum(row["status"] == "qualified" for row in rows),
        "rejected": sum(row["status"].startswith("rejected_") for row in rows),
        "outcomes": len(outcomes),
        "outcome_win_rate": round(sum(item["pnl_pct"] > 0 for item in outcomes) / len(outcomes), 4) if outcomes else None,
        "paper_only": True,
        "broker_submission": False,
    }


def _json(handler: BaseHTTPRequestHandler, value: Any) -> None:
    payload = json.dumps(value, sort_keys=True).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _html(handler: BaseHTTPRequestHandler, value: str) -> None:
    payload = value.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)

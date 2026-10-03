from signalforge.web import build_dashboard_html


def test_dashboard_is_paper_only_and_escapes_signal_text():
    html = build_dashboard_html(
        {"signals": 1, "published": 1, "qualified": 0, "rejected": 0, "outcomes": 0, "outcome_win_rate": None},
        [
            {
                "symbol": "ABCD",
                "direction": "long",
                "strategy_id": "opening-range-breakout",
                "strategy_version": 3,
                "quality_score": 72.5,
                "status": "published",
                "reasons": ["above <VWAP>"],
                "risks": [],
            }
        ],
    )
    assert "PAPER ONLY" in html
    assert "NOT ORDERS" in html
    assert "above &lt;VWAP&gt;" in html
    assert "/api/signals" in html
    assert "No broker connection" in html

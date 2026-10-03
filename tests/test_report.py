from signalforge.report import summarize_outcomes


def test_report_groups_strategy_and_exit_reason_without_prediction_language():
    report = summarize_outcomes(
        [
            {"strategy_id": "orb", "pnl_pct": 1.0, "exit_reason": "target"},
            {"strategy_id": "orb", "pnl_pct": -0.5, "exit_reason": "stop"},
            {"strategy_id": "gap", "pnl_pct": 0.25, "exit_reason": "time_exit"},
        ]
    )
    assert report["paper_only"] is True
    assert report["overall"]["trade_count"] == 3
    assert report["overall"]["win_rate"] == 0.6667
    assert report["by_strategy"]["orb"]["trade_count"] == 2
    assert report["by_exit_reason"] == {"stop": 1, "target": 1, "time_exit": 1}
    assert "not a prediction" in report["note"]

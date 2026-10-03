from datetime import date

from signalforge.validation import (
    build_walk_forward_windows,
    check_no_lookahead,
    sensitivity_report,
    walk_forward_report,
)


def signal(event_id, source, score=70):
    return {"event_id": event_id, "source_timestamp": source, "quality_score": score}


def outcome(event_id, entry, exit_ts, pnl):
    return {"event_id": event_id, "entry_timestamp": entry, "exit_timestamp": exit_ts, "pnl_pct": pnl}


def test_walk_forward_windows_are_ordered_and_non_overlapping():
    windows = build_walk_forward_windows(date(2026, 1, 1), date(2026, 2, 15), train_days=20, test_days=5)
    assert windows[0].train_start == date(2026, 1, 1)
    assert windows[0].test_start == date(2026, 1, 21)
    assert windows[0].test_end == date(2026, 1, 25)
    assert windows[1].test_start > windows[0].test_end


def test_lookahead_check_catches_entry_before_signal():
    signals = [signal("a", "2026-01-10T14:30:00Z")]
    outcomes = [outcome("a", "2026-01-10T14:29:00Z", "2026-01-10T14:40:00Z", 1)]
    errors = check_no_lookahead(signals, outcomes)
    assert errors and "before" in errors[0]


def test_walk_forward_report_is_clean_and_sensitivity_is_descriptive():
    signals = [
        signal("a", "2026-01-22T14:30:00Z", 80),
        signal("b", "2026-01-23T14:30:00Z", 55),
    ]
    outcomes = [
        outcome("a", "2026-01-22T14:31:00Z", "2026-01-22T14:40:00Z", 1),
        outcome("b", "2026-01-23T14:31:00Z", "2026-01-23T14:40:00Z", -0.5),
    ]
    windows = build_walk_forward_windows(date(2026, 1, 1), date(2026, 1, 30), train_days=20, test_days=5)
    report = walk_forward_report(signals, outcomes, windows)
    assert report["clean"] is True
    assert report["paper_only"] is True
    sensitivity = sensitivity_report(signals, outcomes, [50, 70])
    assert sensitivity["thresholds"][0]["metrics"]["trade_count"] == 2
    assert sensitivity["thresholds"][1]["metrics"]["trade_count"] == 1
    assert "no threshold is a recommendation" in sensitivity["note"]

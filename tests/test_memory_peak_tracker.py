"""memory_peak_tracker のピーク記録。"""

import time
from unittest.mock import patch

from utils.memory_peak_tracker import MemoryPeakTracker, format_memory_peak_for_discord


def test_format_memory_peak_for_discord():
    assert format_memory_peak_for_discord(None) == "（未取得）"
    assert format_memory_peak_for_discord({}) == "（未取得）"
    line = format_memory_peak_for_discord(
        {"peak_usage_mb": 1100.5, "limit_mb": 1536.0, "peak_ratio": 0.7165}
    )
    assert "1100.5" in line
    assert "1536" in line
    assert "71.7%" in line


def test_memory_peak_tracker_records_max():
    samples = [
        {"usage_mb": 400.0, "usage_ratio": 0.26, "limit_mb": 1536.0},
        {"usage_mb": 900.0, "usage_ratio": 0.59, "limit_mb": 1536.0},
        {"usage_mb": 750.0, "usage_ratio": 0.49, "limit_mb": 1536.0},
    ]
    idx = {"i": 0}

    def fake_status():
        i = idx["i"]
        idx["i"] = min(i + 1, len(samples) - 1)
        return samples[i]

    tracker = MemoryPeakTracker(interval_sec=0.05)
    with patch("utils.memory_watchdog.get_memory_status", side_effect=fake_status):
        tracker.start()
        time.sleep(0.2)
        summary = tracker.stop()

    assert summary["peak_usage_mb"] == 900.0
    assert summary["peak_ratio"] == 0.59
    assert summary["limit_mb"] == 1536.0
    assert summary["sample_count"] >= 2


def test_memory_peak_tracker_stop_is_idempotent():
    with patch(
        "utils.memory_watchdog.get_memory_status",
        return_value={"usage_mb": 100.0, "usage_ratio": 0.1, "limit_mb": 1024.0},
    ):
        tracker = MemoryPeakTracker(interval_sec=60.0)
        tracker.start()
        first = tracker.stop()
        second = tracker.stop()
    assert first == second
    assert first["peak_usage_mb"] == 100.0

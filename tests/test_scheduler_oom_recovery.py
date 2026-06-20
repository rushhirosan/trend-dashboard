"""OOM ロック回収の DB 補助とサーキットブレーカー。"""

from unittest.mock import MagicMock

import pytest

from database_config import TrendsCache


def test_oom_recovery_slot_key_helpers():
    assert TrendsCache.oom_recovery_slot_prefix("7am_2026-06-20") == "oom_rec_7am_2026-06-20_"
    assert TrendsCache.oom_circuit_open_slot_key("7am_2026-06-20") == "oom_open_7am_2026-06-20"
    assert TrendsCache.oom_recovery_alert_slot_key("7am_2026-06-20") == "oom_alert_7am_2026-06-20"


def test_record_oom_lock_recovery_increments():
    db = TrendsCache.__new__(TrendsCache)
    db.mark_slot_completed = MagicMock()
    db.count_oom_lock_recoveries = MagicMock(side_effect=[0, 1, 2])
    assert db.record_oom_lock_recovery("7am_2026-06-20") == 1
    db.mark_slot_completed.assert_called_once_with("oom_rec_7am_2026-06-20_001")


def test_is_oom_circuit_open_delegates():
    db = TrendsCache.__new__(TrendsCache)
    db.has_slot_completed = MagicMock(return_value=True)
    assert db.is_oom_circuit_open("7am_2026-06-20") is True
    db.has_slot_completed.assert_called_once_with("oom_open_7am_2026-06-20")


def test_is_oom_fetch_blocked_when_circuit_open():
    db = TrendsCache.__new__(TrendsCache)
    db.is_oom_circuit_open = MagicMock(return_value=True)
    blocked = bool(
        db.is_oom_circuit_open("7am_2026-06-20")
    )
    assert blocked is True

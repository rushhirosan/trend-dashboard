"""OOM 後の stale scheduler lock 回収ロジックのテスト。"""

import os
import socket

from utils.scheduler_lock import is_local_holder_process_dead, parse_scheduler_lock_holder


def test_parse_scheduler_lock_holder():
    assert parse_scheduler_lock_holder("e82d4d4a44e758-696-1780092000") == (
        "e82d4d4a44e758",
        696,
    )
    assert parse_scheduler_lock_holder("") is None
    assert parse_scheduler_lock_holder("invalid") is None


def test_is_local_holder_process_dead_current_pid():
    host = socket.gethostname()
    holder = f"{host}-{os.getpid()}-12345"
    assert is_local_holder_process_dead(holder) is False


def test_is_local_holder_process_dead_other_host():
    assert is_local_holder_process_dead("other-machine-999-12345") is False


def test_is_local_holder_process_dead_nonexistent_pid():
    host = socket.gethostname()
    holder = f"{host}-999999999-12345"
    assert is_local_holder_process_dead(holder) is True

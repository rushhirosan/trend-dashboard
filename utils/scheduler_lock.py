"""スケジューラ DB 分散ロックの holder_id 解析・生存確認。"""

import os
import socket


def parse_scheduler_lock_holder(holder_id: str):
    """holder_id（hostname-pid-unix_ts）を分解。形式不明時は None。"""
    if not holder_id:
        return None
    parts = holder_id.rsplit("-", 2)
    if len(parts) != 3:
        return None
    host, pid_str, _ts_str = parts
    try:
        return host, int(pid_str)
    except ValueError:
        return None


def is_local_holder_process_dead(holder_id: str) -> bool:
    """同一ホスト上で holder の PID が存在しない（OOM 等で終了）なら True。"""
    parsed = parse_scheduler_lock_holder(holder_id)
    if not parsed:
        return False
    host, pid = parsed
    if host != socket.gethostname():
        return False
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True

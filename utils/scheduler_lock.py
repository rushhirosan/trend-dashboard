"""スケジューラ DB 分散ロックの holder_id 解析・生存確認。"""

import os
import socket
import time


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


def scheduler_lock_holder_unix_ts(holder_id: str) -> int | None:
    """holder_id に含まれるロック取得時刻（Unix 秒）。"""
    if not holder_id:
        return None
    parts = holder_id.rsplit("-", 2)
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def current_process_start_unix() -> float | None:
    """このプロセスの起動時刻（Unix 秒）。Linux /proc が無い場合は None。"""
    try:
        with open("/proc/self/stat", encoding="utf-8") as f:
            stat = f.read()
        close = stat.rfind(")")
        if close < 0:
            return None
        after = stat[close + 1 :].split()
        starttime_ticks = int(after[19])
        with open("/proc/uptime", encoding="utf-8") as f:
            uptime = float(f.read().split()[0])
        clock_ticks = os.sysconf("SC_CLK_TCK")
        if not clock_ticks:
            return None
        return time.time() - uptime + (starttime_ticks / clock_ticks)
    except (OSError, ValueError, IndexError, TypeError):
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
        # デプロイ直後は gunicorn worker PID が再利用されうる。
        # ロック取得時刻がこのプロセス起動より前なら、前プロセスの stale lock。
        lock_ts = scheduler_lock_holder_unix_ts(holder_id)
        start_ts = current_process_start_unix()
        if lock_ts is not None and start_ts is not None and lock_ts < (start_ts - 1):
            return True
        return False
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True

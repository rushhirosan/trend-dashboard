"""
メモリ逼迫検知（OOM 直前の警告を Discord へ）。

カーネルによる OOM killer（SIGKILL）が走った瞬間には Python は動かないため、
「Out of memory」行そのものはアプリ内では捕捉できない。cgroup の上限に対する RSS 比率で事前警告する。
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from utils.logger_config import get_logger

logger = get_logger(__name__)

_last_alert_ts: dict[str, float] = {}


def _read_cgroup_memory_limit_bytes() -> int | None:
    """cgroup v2 の memory.max を読む。max のときは None。"""
    try:
        with open("/sys/fs/cgroup/memory.max", encoding="utf-8") as f:
            raw = f.read().strip()
        if raw == "max":
            return None
        return int(raw)
    except (OSError, ValueError):
        return None


def _read_rss_bytes() -> int | None:
    """現在プロセスの VmRSS（/proc/self/status）。"""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024  # kB -> bytes
    except (OSError, ValueError, IndexError):
        return None
    return None


def _fallback_limit_bytes() -> int:
    """cgroup が取れない環境用（ローカル等）。env MEMORY_LIMIT_MB または 512。"""
    try:
        mb = int(os.getenv("MEMORY_LIMIT_MB", "512"))
        return max(64, mb) * 1024 * 1024
    except ValueError:
        return 512 * 1024 * 1024


def get_memory_status() -> dict[str, Any]:
    """GET /api/alert/test 用: RSS・上限・比率（監視・デバッグ用）。"""
    rss = _read_rss_bytes()
    limit = _read_cgroup_memory_limit_bytes()
    if limit is None:
        limit = _fallback_limit_bytes()
        limit_source = "fallback(MEMORY_LIMIT_MB or 512)"
    else:
        limit_source = "cgroup memory.max"
    ratio = (rss / limit) if rss is not None and limit else None
    return {
        "rss_bytes": rss,
        "rss_mb": round(rss / (1024 * 1024), 1) if rss is not None else None,
        "limit_bytes": limit,
        "limit_mb": round(limit / (1024 * 1024), 1),
        "limit_source": limit_source,
        "usage_ratio": round(ratio, 4) if ratio is not None else None,
    }


def _should_send(level: str, cooldown_sec: float) -> bool:
    now = time.monotonic()
    last = _last_alert_ts.get(level, 0.0)
    if now - last < cooldown_sec:
        return False
    _last_alert_ts[level] = now
    return True


def _memory_watchdog_loop(
    warn_ratio: float,
    critical_ratio: float,
    interval_sec: float,
    cooldown_sec: float,
) -> None:
    from utils.alert_service import AlertService

    svc = AlertService()
    if not svc.webhook_url:
        logger.info("memory_watchdog: DISCORD_WEBHOOK_URL なしのためスキップ")
        return

    logger.info(
        "memory_watchdog: 開始 (warn=%.0f%% critical=%.0f%% interval=%ss)",
        warn_ratio * 100,
        critical_ratio * 100,
        interval_sec,
    )

    while True:
        try:
            time.sleep(interval_sec)
            st = get_memory_status()
            rss = st.get("rss_bytes")
            limit = st.get("limit_bytes")
            if rss is None or not limit:
                continue
            ratio = rss / limit

            if ratio >= critical_ratio:
                if not _should_send("critical", cooldown_sec):
                    continue
                svc.send_alert(
                    "critical",
                    "メモリ逼迫（OOM 直前の可能性）",
                    "プロセスの RSS が cgroup 上限に近づいています。まもなく OOM でワーカーが落ちると、スケジューラ完了の Discord は届きません。\n"
                    "対策: 取得バッチの軽量化・分割、または VM メモリ増（課金）を検討してください。",
                    {
                        "RSS_MB": str(st.get("rss_mb")),
                        "上限_MB": str(st.get("limit_mb")),
                        "使用率": f"{ratio:.1%}",
                        "limit_source": str(st.get("limit_source")),
                    },
                )
                logger.warning(
                    "memory_watchdog: critical ratio=%.2f rss_mb=%s limit_mb=%s",
                    ratio,
                    st.get("rss_mb"),
                    st.get("limit_mb"),
                )
            elif ratio >= warn_ratio:
                if not _should_send("warning", cooldown_sec):
                    continue
                svc.send_alert(
                    "warning",
                    "メモリ使用率が高い",
                    "一括取得などでメモリを多く使っています。続くと OOM のリスクがあります。",
                    {
                        "RSS_MB": str(st.get("rss_mb")),
                        "上限_MB": str(st.get("limit_mb")),
                        "使用率": f"{ratio:.1%}",
                        "limit_source": str(st.get("limit_source")),
                    },
                )
                logger.warning(
                    "memory_watchdog: warning ratio=%.2f rss_mb=%s limit_mb=%s",
                    ratio,
                    st.get("rss_mb"),
                    st.get("limit_mb"),
                )
        except Exception as e:
            logger.warning("memory_watchdog: ループエラー（継続）: %s", e, exc_info=True)


def start_memory_watchdog() -> None:
    """バックグラウンドスレッドでメモリ監視を開始（gunicorn worker ごとに1本）。"""
    if os.getenv("DISCORD_MEMORY_PRESSURE_ALERT", "true").lower() not in ("1", "true", "yes"):
        logger.info("memory_watchdog: DISCORD_MEMORY_PRESSURE_ALERT で無効")
        return
    if not os.getenv("DISCORD_WEBHOOK_URL", "").strip():
        logger.info("memory_watchdog: Webhook 未設定のためスキップ")
        return

    try:
        warn_ratio = float(os.getenv("MEMORY_PRESSURE_WARN_RATIO", "0.82"))
        critical_ratio = float(os.getenv("MEMORY_PRESSURE_CRITICAL_RATIO", "0.90"))
        interval_sec = float(os.getenv("MEMORY_WATCHDOG_INTERVAL_SEC", "45"))
        cooldown_sec = float(os.getenv("MEMORY_PRESSURE_ALERT_COOLDOWN_SEC", "1200"))
    except ValueError:
        warn_ratio, critical_ratio, interval_sec, cooldown_sec = 0.82, 0.90, 45.0, 1200.0

    warn_ratio = min(0.99, max(0.5, warn_ratio))
    critical_ratio = min(0.99, max(warn_ratio + 0.01, critical_ratio))
    interval_sec = max(15.0, interval_sec)
    cooldown_sec = max(60.0, cooldown_sec)

    t = threading.Thread(
        target=_memory_watchdog_loop,
        args=(warn_ratio, critical_ratio, interval_sec, cooldown_sec),
        name="memory-watchdog",
        daemon=True,
    )
    t.start()

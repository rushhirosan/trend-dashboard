"""
ジョブ実行中の cgroup メモリピークをバックグラウンドで記録する。

定時取得完了 Discord にピークを載せる用途。memory_watchdog と同じ get_memory_status を使う。
"""

from __future__ import annotations

import os
import threading
from typing import Any

from utils.logger_config import get_logger

logger = get_logger(__name__)


def _default_interval_sec() -> float:
    try:
        return max(10.0, float(os.getenv("MEMORY_WATCHDOG_INTERVAL_SEC", "15")))
    except ValueError:
        return 15.0


def format_memory_peak_for_discord(peak: dict[str, Any] | None) -> str:
    """Discord details 用の1行表示。"""
    if not peak:
        return "（未取得）"
    peak_mb = peak.get("peak_usage_mb")
    if peak_mb is None:
        return "（未取得）"
    limit_mb = peak.get("limit_mb")
    ratio = peak.get("peak_ratio")
    if limit_mb is not None and ratio is not None:
        return f"{peak_mb} / {limit_mb} MB ({ratio:.1%})"
    return f"{peak_mb} MB"


class MemoryPeakTracker:
    """バックグラウンドで usage_mb の最大値を記録する。"""

    def __init__(self, *, interval_sec: float | None = None) -> None:
        self._interval = interval_sec if interval_sec is not None else _default_interval_sec()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._peak_usage_mb: float | None = None
        self._peak_ratio: float | None = None
        self._limit_mb: float | None = None
        self._sample_count = 0

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._sample_once()
        self._thread = threading.Thread(
            target=self._loop,
            name="memory-peak-tracker",
            daemon=True,
        )
        self._thread.start()
        logger.debug("memory_peak_tracker: 開始 (interval=%ss)", self._interval)

    def stop(self) -> dict[str, Any]:
        if self._started:
            self._stop_event.set()
            if self._thread is not None:
                self._thread.join(timeout=2.0)
            self._sample_once()
            self._started = False
            logger.debug(
                "memory_peak_tracker: 停止 peak_mb=%s samples=%s",
                self._peak_usage_mb,
                self._sample_count,
            )
        return self.summary()

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "peak_usage_mb": self._peak_usage_mb,
                "peak_ratio": self._peak_ratio,
                "limit_mb": self._limit_mb,
                "sample_count": self._sample_count,
            }

    def _loop(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self._sample_once()
            except Exception as e:
                logger.debug("memory_peak_tracker: sample error: %s", e)

    def _sample_once(self) -> None:
        from utils.memory_watchdog import get_memory_status

        st = get_memory_status()
        usage_mb = st.get("usage_mb")
        if usage_mb is None:
            return
        ratio = st.get("usage_ratio")
        limit_mb = st.get("limit_mb")
        with self._lock:
            self._sample_count += 1
            if self._limit_mb is None and limit_mb is not None:
                self._limit_mb = limit_mb
            if self._peak_usage_mb is None or usage_mb > self._peak_usage_mb:
                self._peak_usage_mb = usage_mb
                self._peak_ratio = ratio

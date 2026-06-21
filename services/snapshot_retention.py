"""trend_daily_snapshots / scheduler_slot_run の保持日数を超えた行を削除する。"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import pytz

from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = pytz.timezone("Asia/Tokyo")

DEFAULT_RETENTION_DAYS = 10
MIN_RETENTION_DAYS = 7
MAX_RETENTION_DAYS = 90


def retention_enabled() -> bool:
    return os.getenv("TREND_SNAPSHOT_RETENTION_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def retention_days() -> int:
    raw = os.getenv("TREND_SNAPSHOT_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, days))


def snapshot_cutoff_business_day(
    *,
    today: Optional[date] = None,
    days: Optional[int] = None,
) -> date:
    """この日より古い business_day のスナップショットを削除対象とする（未満）。"""
    ref = today or datetime.now(JST).date()
    keep = days if days is not None else retention_days()
    return ref - timedelta(days=keep)


def scheduler_slot_cutoff(
    *,
    now: Optional[datetime] = None,
    days: Optional[int] = None,
) -> datetime:
    """この時刻より古い scheduler_slot_run を削除対象とする（未満）。"""
    ref = now or datetime.now(JST)
    if ref.tzinfo is None:
        ref = JST.localize(ref)
    else:
        ref = ref.astimezone(JST)
    keep = days if days is not None else retention_days()
    return ref - timedelta(days=keep)


def purge_expired_snapshots(
    db: Optional[TrendsCache] = None,
    *,
    days: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    保持日数を超えた trend_daily_snapshots と scheduler_slot_run を削除する。

    Returns:
        dict with keys: enabled, dry_run, retention_days, snapshot_cutoff,
        scheduler_cutoff, snapshots_deleted, scheduler_rows_deleted, ok
    """
    keep_days = days if days is not None else retention_days()
    cutoff_day = snapshot_cutoff_business_day(days=keep_days)
    cutoff_ts = scheduler_slot_cutoff(days=keep_days)

    result: Dict[str, Any] = {
        "enabled": retention_enabled(),
        "dry_run": dry_run,
        "retention_days": keep_days,
        "snapshot_cutoff": cutoff_day.isoformat(),
        "scheduler_cutoff": cutoff_ts.isoformat(),
        "snapshots_deleted": 0,
        "scheduler_rows_deleted": 0,
        "ok": True,
    }

    if not result["enabled"]:
        logger.info("⏭️ スナップショット保持期間クリーンアップは無効（TREND_SNAPSHOT_RETENTION_ENABLED=false）")
        return result

    cache = db or TrendsCache()

    if dry_run:
        if hasattr(cache, "count_trend_daily_snapshots_older_than"):
            result["snapshots_deleted"] = cache.count_trend_daily_snapshots_older_than(
                cutoff_day
            )
        if hasattr(cache, "count_scheduler_slot_run_older_than"):
            result["scheduler_rows_deleted"] = cache.count_scheduler_slot_run_older_than(
                cutoff_ts
            )
        logger.info(
            "🔍 スナップショット保持クリーンアップ dry-run: snapshots=%s scheduler_slot_run=%s cutoff_day=%s",
            result["snapshots_deleted"],
            result["scheduler_rows_deleted"],
            cutoff_day.isoformat(),
        )
        return result

    try:
        if hasattr(cache, "purge_trend_daily_snapshots_older_than"):
            result["snapshots_deleted"] = cache.purge_trend_daily_snapshots_older_than(
                cutoff_day
            )
        if hasattr(cache, "purge_scheduler_slot_run_older_than"):
            result["scheduler_rows_deleted"] = cache.purge_scheduler_slot_run_older_than(
                cutoff_ts
            )
    except Exception as e:
        logger.error("❌ スナップショット保持クリーンアップ失敗: %s", e, exc_info=True)
        result["ok"] = False

    if result["ok"]:
        logger.info(
            "🧹 スナップショット保持クリーンアップ完了: snapshots=%s scheduler_slot_run=%s retention=%s日 cutoff=%s",
            result["snapshots_deleted"],
            result["scheduler_rows_deleted"],
            keep_days,
            cutoff_day.isoformat(),
        )
    return result

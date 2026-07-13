"""DB スナップショットと docs/summaries 原稿の保持期間超過分を削除する。"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = ZoneInfo("Asia/Tokyo")

DEFAULT_RETENTION_DAYS = 10
MIN_RETENTION_DAYS = 7
MAX_RETENTION_DAYS = 90

DEFAULT_WEEKLY_RETENTION_DAYS = 30
MIN_WEEKLY_RETENTION_DAYS = 7
MAX_WEEKLY_RETENTION_DAYS = 365

_DAILY_SUMMARY_RE = re.compile(
    r"^(?P<day>\d{4}-\d{2}-\d{2})(?:\.md|\.generation\.json)$"
)
_WEEKLY_SUMMARY_RE = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})\.md$")


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


def daily_summary_retention_days() -> int:
    raw = os.getenv("SUMMARY_DAILY_RETENTION_DAYS")
    if raw is None or str(raw).strip() == "":
        return retention_days()
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = retention_days()
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, days))


def weekly_summary_retention_days() -> int:
    raw = os.getenv("SUMMARY_WEEKLY_RETENTION_DAYS", str(DEFAULT_WEEKLY_RETENTION_DAYS))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_WEEKLY_RETENTION_DAYS
    return max(MIN_WEEKLY_RETENTION_DAYS, min(MAX_WEEKLY_RETENTION_DAYS, days))


def summaries_base_dir(base: Optional[Path] = None) -> Path:
    if base is not None:
        return base
    env_root = os.getenv("TREND_DASHBOARD_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root) / "docs" / "summaries"
    return Path(__file__).resolve().parent.parent / "docs" / "summaries"


def snapshot_cutoff_business_day(
    *,
    today: Optional[date] = None,
    days: Optional[int] = None,
) -> date:
    """この日より古い business_day のスナップショットを削除対象とする（未満）。"""
    ref = today or datetime.now(JST).date()
    keep = days if days is not None else retention_days()
    return ref - timedelta(days=keep)


def daily_summary_cutoff_business_day(
    *,
    today: Optional[date] = None,
    days: Optional[int] = None,
) -> date:
    ref = today or datetime.now(JST).date()
    keep = days if days is not None else daily_summary_retention_days()
    return ref - timedelta(days=keep)


def weekly_summary_cutoff(
    *,
    today: Optional[date] = None,
    days: Optional[int] = None,
) -> date:
    """ISO 週の月曜がこの日より古い週次ファイルを削除対象とする（未満）。"""
    ref = today or datetime.now(JST).date()
    keep = days if days is not None else weekly_summary_retention_days()
    return ref - timedelta(days=keep)


def scheduler_slot_cutoff(
    *,
    now: Optional[datetime] = None,
    days: Optional[int] = None,
) -> datetime:
    """この時刻より古い scheduler_slot_run を削除対象とする（未満）。"""
    ref = now or datetime.now(JST)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=JST)
    else:
        ref = ref.astimezone(JST)
    keep = days if days is not None else retention_days()
    return ref - timedelta(days=keep)


def _parse_daily_summary_date(filename: str) -> Optional[date]:
    match = _DAILY_SUMMARY_RE.match(filename)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group("day"))
    except ValueError:
        return None


def _parse_weekly_summary_monday(filename: str) -> Optional[date]:
    match = _WEEKLY_SUMMARY_RE.match(filename)
    if not match:
        return None
    try:
        return date.fromisocalendar(
            int(match.group("year")),
            int(match.group("week")),
            1,
        )
    except ValueError:
        return None


def collect_expired_summary_files(
    summaries_dir: Optional[Path] = None,
    *,
    today: Optional[date] = None,
    daily_days: Optional[int] = None,
    weekly_days: Optional[int] = None,
) -> Tuple[List[Path], List[Path]]:
    """削除対象の日次・週次サマリーファイルパスを返す。"""
    base = summaries_base_dir(summaries_dir)
    daily_dir = base / "daily"
    weekly_dir = base / "weekly"
    daily_cutoff = daily_summary_cutoff_business_day(today=today, days=daily_days)
    weekly_cutoff = weekly_summary_cutoff(today=today, days=weekly_days)

    expired_daily: List[Path] = []
    expired_weekly: List[Path] = []

    def _scan_dirs(base: Path) -> List[Path]:
        """base 直下と、リージョン用サブディレクトリ（例 us/）を対象にする。"""
        dirs = [base]
        if base.is_dir():
            dirs.extend(sorted(p for p in base.iterdir() if p.is_dir()))
        return dirs

    for d in _scan_dirs(daily_dir):
        if not d.is_dir():
            continue
        for path in sorted(d.iterdir()):
            if not path.is_file():
                continue
            day = _parse_daily_summary_date(path.name)
            if day is None:
                continue
            if day < daily_cutoff:
                expired_daily.append(path)

    for d in _scan_dirs(weekly_dir):
        if not d.is_dir():
            continue
        for path in sorted(d.iterdir()):
            if not path.is_file():
                continue
            monday = _parse_weekly_summary_monday(path.name)
            if monday is None:
                continue
            if monday < weekly_cutoff:
                expired_weekly.append(path)

    return expired_daily, expired_weekly


def purge_expired_summary_files(
    summaries_dir: Optional[Path] = None,
    *,
    today: Optional[date] = None,
    daily_days: Optional[int] = None,
    weekly_days: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    expired_daily, expired_weekly = collect_expired_summary_files(
        summaries_dir,
        today=today,
        daily_days=daily_days,
        weekly_days=weekly_days,
    )
    deleted_daily: List[str] = []
    deleted_weekly: List[str] = []

    if not dry_run:
        for path in expired_daily:
            try:
                path.unlink(missing_ok=True)
                deleted_daily.append(str(path))
            except OSError as e:
                logger.warning("⚠️ 日次サマリー削除失敗 %s: %s", path, e)
        for path in expired_weekly:
            try:
                path.unlink(missing_ok=True)
                deleted_weekly.append(str(path))
            except OSError as e:
                logger.warning("⚠️ 週次サマリー削除失敗 %s: %s", path, e)

    return {
        "daily_summary_cutoff": daily_summary_cutoff_business_day(
            today=today, days=daily_days
        ).isoformat(),
        "weekly_summary_cutoff": weekly_summary_cutoff(
            today=today, days=weekly_days
        ).isoformat(),
        "daily_summary_files_deleted": len(expired_daily if dry_run else deleted_daily),
        "weekly_summary_files_deleted": len(expired_weekly if dry_run else deleted_weekly),
        "daily_summary_paths": [str(p) for p in expired_daily],
        "weekly_summary_paths": [str(p) for p in expired_weekly],
    }


def purge_expired_snapshots(
    db: Optional[TrendsCache] = None,
    *,
    days: Optional[int] = None,
    daily_summary_days: Optional[int] = None,
    weekly_summary_days: Optional[int] = None,
    summaries_dir: Optional[Path] = None,
    purge_summary_files: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    保持日数を超えた trend_daily_snapshots / scheduler_slot_run /
    docs/summaries の日次・週次 Markdown を削除する。

    日次原稿は GitHub Actions がリポジトリにコミットするため、
    docs/summaries の削除を git に反映するには手元または CI で本スクリプトを実行する。
    """
    keep_days = days if days is not None else retention_days()
    cutoff_day = snapshot_cutoff_business_day(days=keep_days)
    cutoff_ts = scheduler_slot_cutoff(days=keep_days)

    result: Dict[str, Any] = {
        "enabled": retention_enabled(),
        "dry_run": dry_run,
        "retention_days": keep_days,
        "daily_summary_retention_days": daily_summary_days
        if daily_summary_days is not None
        else daily_summary_retention_days(),
        "weekly_summary_retention_days": weekly_summary_days
        if weekly_summary_days is not None
        else weekly_summary_retention_days(),
        "snapshot_cutoff": cutoff_day.isoformat(),
        "scheduler_cutoff": cutoff_ts.isoformat(),
        "snapshots_deleted": 0,
        "scheduler_rows_deleted": 0,
        "daily_summary_files_deleted": 0,
        "weekly_summary_files_deleted": 0,
        "daily_summary_cutoff": None,
        "weekly_summary_cutoff": None,
        "ok": True,
    }

    if not result["enabled"]:
        logger.info("⏭️ スナップショット保持クリーンアップは無効（TREND_SNAPSHOT_RETENTION_ENABLED=false）")
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
    else:
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

    if purge_summary_files and result["ok"]:
        try:
            summary_result = purge_expired_summary_files(
                summaries_dir,
                daily_days=daily_summary_days,
                weekly_days=weekly_summary_days,
                dry_run=dry_run,
            )
            result["daily_summary_cutoff"] = summary_result["daily_summary_cutoff"]
            result["weekly_summary_cutoff"] = summary_result["weekly_summary_cutoff"]
            result["daily_summary_files_deleted"] = summary_result[
                "daily_summary_files_deleted"
            ]
            result["weekly_summary_files_deleted"] = summary_result[
                "weekly_summary_files_deleted"
            ]
        except Exception as e:
            logger.error("❌ サマリー原稿クリーンアップ失敗: %s", e, exc_info=True)
            result["ok"] = False

    if result["ok"]:
        logger.info(
            "🧹 保持クリーンアップ%s: snapshots=%s scheduler_slot_run=%s "
            "daily_md=%s weekly_md=%s snapshot_cutoff=%s daily_cutoff=%s weekly_cutoff=%s",
            " (dry-run)" if dry_run else "完了",
            result["snapshots_deleted"],
            result["scheduler_rows_deleted"],
            result["daily_summary_files_deleted"],
            result["weekly_summary_files_deleted"],
            cutoff_day.isoformat(),
            result.get("daily_summary_cutoff"),
            result.get("weekly_summary_cutoff"),
        )
    return result

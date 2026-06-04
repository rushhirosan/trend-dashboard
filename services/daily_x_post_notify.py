"""
19 時 JST スケジューラ完了後に X 投稿案を Discord へ送る。

トリガーは ``TrendsScheduler`` の 7pm スロット成功時のみ（``ENABLE_EVENING_X_POST_DISCORD``）。
同一 business_day への重複送信は ``scheduler_slot_run`` の ``xpost_discord_{date}`` で防止。
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def xpost_discord_dedup_key(business_day_iso: str) -> str:
    return f"xpost_discord_{business_day_iso}"


def _import_x_post_modules():
    scripts = str(_SCRIPTS_DIR)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import generate_daily_x_post_series as gx  # noqa: PLC0415
    import daily_x_post_discord as dxd  # noqa: PLC0415

    return gx, dxd


def run_evening_x_post_discord_notify(db: Any | None = None) -> bool:
    """
    スナップショット 07/13/19 から JP/US 文案（記事 URL 付き）を生成し Discord に POST。
    成功時 True。送信済み・設定無効・失敗時 False。
    """
    if os.getenv("ENABLE_EVENING_X_POST_DISCORD", "true").lower() not in (
        "1",
        "true",
        "yes",
    ):
        logger.info("evening_x_post: ENABLE_EVENING_X_POST_DISCORD で無効")
        return False

    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        logger.warning("evening_x_post: DATABASE_URL なしのためスキップ")
        return False

    gx, dxd = _import_x_post_modules()
    business_day = gx.default_business_day_for_evening_x_post_jst()
    day_s = business_day.isoformat()
    dedup_key = xpost_discord_dedup_key(day_s)

    if db is not None and hasattr(db, "has_slot_completed") and db.has_slot_completed(dedup_key):
        logger.info("evening_x_post: 本日 Discord 送信済み (%s)", dedup_key)
        return False

    try:
        series_by_slot = gx.load_snapshots_daytime_slots(database_url, business_day)
        gx._validate_daytime_snapshot_bundle(
            series_by_slot,
            business_day,
            required_slots=gx.SNAPSHOT_SLOTS_DAYTIME,
        )
    except Exception as e:
        logger.error("evening_x_post: スナップショット読込失敗: %s", e, exc_info=True)
        return False

    try:
        jp = gx.build_jp_block_from_snapshots(
            series_by_slot, day_s, include_article_links=True
        )
        us = gx.build_us_block_from_snapshots(
            series_by_slot, day_s, include_article_links=True
        )
    except ValueError as e:
        logger.error("evening_x_post: 文案生成失敗: %s", e)
        return False

    webhook = dxd.resolve_discord_webhook_url()
    if not webhook:
        logger.warning("evening_x_post: DISCORD_WEBHOOK_URL 未設定のためスキップ")
        return False

    try:
        dxd.notify_daily_x_post_discord(webhook, day_s, jp, us)
    except Exception as e:
        logger.error("evening_x_post: Discord 送信失敗: %s", e, exc_info=True)
        return False

    if db is not None and hasattr(db, "mark_slot_completed"):
        db.mark_slot_completed(dedup_key)

    logger.info("evening_x_post: Discord 送信完了 business_day=%s", day_s)
    return True


def schedule_evening_x_post_discord_notify(db: Any | None = None) -> None:
    """スケジューラ完了処理をブロックしないようバックグラウンドで実行。"""
    threading.Thread(
        target=run_evening_x_post_discord_notify,
        args=(db,),
        name="evening-x-post-discord",
        daemon=True,
    ).start()

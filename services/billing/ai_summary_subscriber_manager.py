"""有料 AI サマリー購読者（Stripe Checkout 後）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from database_config import TrendsCache
from services.billing.region_plan import normalize_region_plan
from utils.logger_config import get_logger

logger = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class AiSummarySubscriberManager:
    """ai_summary_subscribers テーブル。"""

    def __init__(self) -> None:
        self.db = TrendsCache()
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS ai_summary_subscribers (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) NOT NULL UNIQUE,
                            region_plan VARCHAR(8) NOT NULL DEFAULT 'jp',
                            stripe_customer_id VARCHAR(255),
                            stripe_subscription_id VARCHAR(255),
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_ai_summary_subscribers_active "
                        "ON ai_summary_subscribers(is_active)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_ai_summary_subscribers_region "
                        "ON ai_summary_subscribers(region_plan)"
                    )
                    conn.commit()
                    logger.info("✅ ai_summary_subscribers テーブル確認完了")
        except Exception as e:
            logger.warning("⚠️ ai_summary_subscribers テーブル作成エラー: %s", e)

    @staticmethod
    def validate_email(email: str) -> bool:
        return bool(_EMAIL_RE.match((email or "").strip()))

    def upsert_active(
        self,
        *,
        email: str,
        region_plan: str,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        email_n = (email or "").strip().lower()
        if not self.validate_email(email_n):
            return False, "有効なメールアドレスが必要です"
        plan = normalize_region_plan(region_plan)
        if not plan:
            return False, "region_plan が不正です"

        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO ai_summary_subscribers (
                            email, region_plan, stripe_customer_id,
                            stripe_subscription_id, is_active, updated_at
                        )
                        VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                        ON CONFLICT (email) DO UPDATE SET
                            region_plan = EXCLUDED.region_plan,
                            stripe_customer_id = COALESCE(
                                EXCLUDED.stripe_customer_id,
                                ai_summary_subscribers.stripe_customer_id
                            ),
                            stripe_subscription_id = COALESCE(
                                EXCLUDED.stripe_subscription_id,
                                ai_summary_subscribers.stripe_subscription_id
                            ),
                            is_active = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            email_n,
                            plan,
                            stripe_customer_id,
                            stripe_subscription_id,
                        ),
                    )
                    conn.commit()
            logger.info(
                "📧 AIサマリー有料購読 upsert: %s plan=%s", email_n, plan
            )
            return True, "購読を登録しました"
        except Exception as e:
            logger.error("❌ AIサマリー有料購読 upsert エラー: %s", e, exc_info=True)
            return False, "購読登録に失敗しました"

    def deactivate_by_subscription_id(self, stripe_subscription_id: str) -> bool:
        sub_id = (stripe_subscription_id or "").strip()
        if not sub_id:
            return False
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE ai_summary_subscribers
                        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE stripe_subscription_id = %s
                        """,
                        (sub_id,),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(
                "❌ 購読無効化エラー sub=%s: %s", sub_id, e, exc_info=True
            )
            return False

    def list_active_for_region(self, region: str) -> List[Dict[str, Any]]:
        """指定地域 (jp/us) に配信すべき有効購読者。"""
        region_n = (region or "jp").strip().lower()
        if region_n not in ("jp", "us"):
            return []
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT email, region_plan
                        FROM ai_summary_subscribers
                        WHERE is_active = TRUE
                          AND (region_plan = %s OR region_plan = 'both')
                        ORDER BY email
                        """,
                        (region_n,),
                    )
                    rows = cursor.fetchall()
                    return [
                        {"email": row[0], "region_plan": row[1]} for row in rows
                    ]
        except Exception as e:
            logger.error("❌ 有料購読者一覧エラー: %s", e, exc_info=True)
            return []

    def list_all_active(self) -> List[Dict[str, Any]]:
        """有効購読者（email, region_plan）。GHA 向け API 用。"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT email, region_plan
                        FROM ai_summary_subscribers
                        WHERE is_active = TRUE
                        ORDER BY email
                        """
                    )
                    rows = cursor.fetchall()
                    return [
                        {"email": row[0], "region_plan": row[1]} for row in rows
                    ]
        except Exception as e:
            logger.error("❌ 有料購読者全件エラー: %s", e, exc_info=True)
            return []

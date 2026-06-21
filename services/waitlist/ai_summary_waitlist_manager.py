"""AIサマリー有料版の事前登録（Fake door / Waitlist）"""

import re
from typing import Tuple

from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)


class AiSummaryWaitlistManager:
    """ai_summary_waitlist テーブルへの登録"""

    _EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def __init__(self):
        self.db = TrendsCache()
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS ai_summary_waitlist (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) NOT NULL,
                            region VARCHAR(8) NOT NULL DEFAULT 'jp',
                            source VARCHAR(32) NOT NULL DEFAULT 'fake_door',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE (email)
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_ai_summary_waitlist_region "
                        "ON ai_summary_waitlist(region)"
                    )
                    conn.commit()
                    logger.info("✅ ai_summary_waitlist テーブル確認完了")
        except Exception as e:
            logger.warning("⚠️ ai_summary_waitlist テーブル作成エラー: %s", e)

    def validate_email(self, email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        return bool(self._EMAIL_RE.match(email.strip()))

    def add(self, email: str, region: str, source: str = "fake_door") -> Tuple[bool, str]:
        """
        メールを登録する。同一メールは上書きせず成功として返す（冪等）。
        """
        email = (email or "").strip().lower()
        if not self.validate_email(email):
            return False, "有効なメールアドレスを入力してください"
        if region not in ("jp", "us"):
            return False, "region が不正です"
        src = (source or "fake_door").strip()[:32] or "fake_door"

        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO ai_summary_waitlist (email, region, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (email) DO NOTHING
                        """,
                        (email, region, src),
                    )
                    conn.commit()
            logger.info("📧 AIサマリー waitlist 登録: %s (%s)", email, region)
            return True, "登録を受け付けました。"
        except Exception as e:
            logger.error("❌ AIサマリー waitlist 登録エラー: %s", e, exc_info=True)
            return False, "登録に失敗しました"

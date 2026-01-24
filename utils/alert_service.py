"""
アラート通知サービス
Discord Webhook で更新エラー・異常検出時に通知
"""

import os
from datetime import datetime
import pytz
import requests
from utils.logger_config import get_logger

logger = get_logger(__name__)


class AlertService:
    """Discord Webhook でアラート通知"""

    def __init__(self):
        # 環境変数から取得（秘密情報のためコードに含めない）
        url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        # discordapp.com / discord.com どちらも許容
        if url and "discord" in url:
            self.webhook_url = url
        else:
            self.webhook_url = None

        if self.webhook_url:
            logger.info("🔔 AlertService: Discord Webhook 有効")
        else:
            logger.info("🔔 AlertService: DISCORD_WEBHOOK_URL 未設定のためアラート無効")

    def send_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        details: dict | None = None,
    ) -> bool:
        """
        アラートを Discord に送信

        Args:
            alert_type: 'error' | 'warning' | 'critical'
            title: アラートタイトル
            message: 本文
            details: 追加情報（key -> value）

        Returns:
            送信成功時 True
        """
        if not self.webhook_url:
            logger.debug("DISCORD_WEBHOOK_URL 未設定のためアラート送信をスキップ")
            return False

        try:
            return self._send_discord(alert_type, title, message, details)
        except Exception as e:
            logger.error("Discord アラート送信エラー: %s", e, exc_info=True)
            return False

    def _send_discord(
        self,
        alert_type: str,
        title: str,
        message: str,
        details: dict | None,
    ) -> bool:
        """Discord Webhook に POST"""
        jst = pytz.timezone("Asia/Tokyo")
        now = datetime.now(jst)

        # 色: 10進数 (Discord embed color)
        colors = {
            "error": 15158332,   # 赤
            "warning": 16776960, # 黄
            "critical": 15158332 # 赤
        }
        color = colors.get(alert_type, colors["error"])

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": now.isoformat(),
            "footer": {"text": "Trends Dashboard Alert"},
        }

        if details:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": False}
                for k, v in details.items()
            ]

        payload = {
            "username": "Trends Dashboard Alert",
            "embeds": [embed],
        }

        resp = requests.post(
            self.webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info("✅ Discord アラート送信完了: %s", title)
        return True

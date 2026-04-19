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

# Discord Embed 制限（超過すると Webhook が 400 を返す）
_DISCORD_FIELD_VALUE_MAX = 1020  # 公式 1024 より余裕
_DISCORD_FIELD_NAME_MAX = 256
_DISCORD_FIELDS_PER_EMBED_MAX = 25
_DISCORD_EMBED_BODY_MAX = 5800  # 公式 6000 より余裕（title+description+fields+footer 合算）
_DISCORD_WEBHOOK_EMBEDS_MAX = 10


def _chunk_discord_field_value(text: str, max_len: int = _DISCORD_FIELD_VALUE_MAX) -> list[str]:
    """1フィールドに収まるよう長い文字列を分割する。"""
    if text is None:
        return ["\u200b"]
    s = str(text)
    if not s.strip():
        return ["\u200b"]
    if len(s) <= max_len:
        return [s]
    return [s[i : i + max_len] for i in range(0, len(s), max_len)]


def _details_to_flat_fields(details: dict) -> list[dict]:
    """details を Discord embed fields のフラットリストに変換（値は自動チャンク）。"""
    flat: list[dict] = []
    for k, v in details.items():
        name_base = str(k)[:_DISCORD_FIELD_NAME_MAX]
        chunks = _chunk_discord_field_value(v)
        total = len(chunks)
        for i, ch in enumerate(chunks):
            name = name_base if total == 1 else f"{name_base} ({i + 1}/{total})"[:_DISCORD_FIELD_NAME_MAX]
            flat.append({"name": name, "value": ch[:_DISCORD_FIELD_VALUE_MAX], "inline": False})
    return flat


def _approx_embed_size(embed: dict) -> int:
    """埋め込みのおおよその文字数（フィールド含む）。"""
    n = len(embed.get("title") or "") + len(embed.get("description") or "")
    foot = embed.get("footer") or {}
    n += len((foot.get("text") or ""))
    for f in embed.get("fields") or []:
        n += len(f.get("name") or "") + len(f.get("value") or "")
    return n


def _pack_fields_into_embeds(
    title: str,
    message: str,
    color: int,
    timestamp: str,
    footer_text: str,
    flat_fields: list[dict],
) -> list[dict]:
    """フラットフィールドを複数 embed に分割（25フィールド/6000文字/10 embed 上限）。"""
    embeds: list[dict] = []

    def base_embed(t: str, desc: str, include_footer: bool) -> dict:
        e: dict = {
            "title": t[:256],
            "description": (desc[:4096] if desc else None),
            "color": color,
            "timestamp": timestamp,
        }
        if include_footer:
            e["footer"] = {"text": footer_text[:2048]}
        if e.get("description") is None:
            del e["description"]
        return e

    if not flat_fields:
        return [base_embed(title, message, True)]

    def flush(embed_dict: dict, fields: list[dict]) -> None:
        if not fields:
            return
        e = {**embed_dict, "fields": fields}
        embeds.append(e)

    first_shell = base_embed(title, message, True)
    current_shell = first_shell
    current_fields: list[dict] = []
    size = _approx_embed_size(current_shell)

    fi = 0
    while fi < len(flat_fields):
        if len(embeds) >= _DISCORD_WEBHOOK_EMBEDS_MAX:
            logger.warning(
                "Discord アラート: embed 上限 (%s) のため残り %s フィールドを送信できませんでした",
                _DISCORD_WEBHOOK_EMBEDS_MAX,
                len(flat_fields) - fi,
            )
            break

        field = flat_fields[fi]
        add = len(field.get("name") or "") + len(field.get("value") or "")
        over_fields = len(current_fields) >= _DISCORD_FIELDS_PER_EMBED_MAX
        over_chars = bool(current_fields) and (size + add > _DISCORD_EMBED_BODY_MAX)

        if current_fields and (over_fields or over_chars):
            flush(current_shell, current_fields)
            cont_title = f"{title}（続き {len(embeds)}）"[:256]
            current_shell = base_embed(cont_title, "", False)
            current_fields = []
            size = _approx_embed_size(current_shell)
            continue

        current_fields.append(field)
        size += add
        fi += 1

    if current_fields and len(embeds) < _DISCORD_WEBHOOK_EMBEDS_MAX:
        flush(current_shell, current_fields)
    elif current_fields:
        logger.warning(
            "Discord アラート: embed 上限のため %s フィールドを送信できませんでした",
            len(current_fields),
        )

    return embeds[:_DISCORD_WEBHOOK_EMBEDS_MAX]


class AlertService:
    """Discord Webhook でアラート通知"""

    def __init__(self):
        self.last_send_error: str | None = None
        # 環境変数から取得（秘密情報のためコードに含めない）
        url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        # discordapp.com / discord.com どちらも許容
        if url and "discord" in url.lower():
            self.webhook_url = url
        else:
            self.webhook_url = None
            if url:
                logger.warning(
                    "🔔 AlertService: DISCORD_WEBHOOK_URL は有効な Discord Webhook の URL である必要があります（'discord' を含むこと）"
                )

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
            alert_type: 'error' | 'warning' | 'critical' | 'success'
            title: アラートタイトル
            message: 本文
            details: 追加情報（key -> value）

        Returns:
            送信成功時 True
        """
        if not self.webhook_url:
            logger.debug("DISCORD_WEBHOOK_URL 未設定のためアラート送信をスキップ")
            self.last_send_error = "DISCORD_WEBHOOK_URL 未設定、または URL に discord が含まれません"
            return False

        self.last_send_error = None
        try:
            return self._send_discord(alert_type, title, message, details)
        except Exception as e:
            self.last_send_error = str(e)
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
            "critical": 15158332, # 赤
            "success": 3066993   # 緑
        }
        color = colors.get(alert_type, colors["error"])
        ts = now.isoformat()
        footer_text = "Trends Dashboard Alert"

        # 詳細フィールドありのとき本文が長いと 1 embed 6000 文字を超えるため余白を確保
        body = message
        if details and body and len(body) > 3200:
            body = body[:3190] + "…(省略)"

        flat_fields = _details_to_flat_fields(details) if details else []
        embeds = _pack_fields_into_embeds(title, body, color, ts, footer_text, flat_fields)

        payload = {
            "username": "Trends Dashboard Alert",
            "embeds": embeds,
        }

        resp = requests.post(
            self.webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            body = (resp.text or "")[:2500]
            logger.error(
                "Discord Webhook HTTP %s: %s",
                resp.status_code,
                body,
            )
            raise RuntimeError(f"Discord HTTP {resp.status_code}: {body[:500]}")
        logger.info("✅ Discord アラート送信完了: %s", title)
        return True

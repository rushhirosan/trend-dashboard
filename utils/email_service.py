# メール送信サービス
import json
import smtplib
import os
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

class EmailService:
    def __init__(self):
        # 環境変数からメール設定を読み込む（機密情報は .env で管理）
        # EMAIL_PROVIDER=smtp|gmail → Gmail 等の SMTP
        # EMAIL_PROVIDER=sendgrid → SendGrid Web API
        # EMAIL_PROVIDER=auto（既定）→ Gmail SMTP が揃っていれば SMTP、なければ SendGrid、それ以外は SMTP
        provider = (os.getenv('EMAIL_PROVIDER') or 'auto').strip().lower()
        sendgrid_key = (os.getenv('SENDGRID_API_KEY') or '').strip()
        smtp_server_env = (os.getenv('SMTP_SERVER') or '').strip()
        sender_email = (os.getenv('SENDER_EMAIL') or '').strip()
        sender_password = (os.getenv('SENDER_PASSWORD') or '').strip()
        self.from_email = (
            os.getenv('SENDGRID_FROM_EMAIL')
            or os.getenv('MAIL_FROM')
            or ''
        ).strip()
        self.smtp_port = int((os.getenv('SMTP_PORT') or '587').strip())

        use_sendgrid = False
        if provider in ('sendgrid', 'sg'):
            use_sendgrid = bool(sendgrid_key)
        elif provider in ('smtp', 'gmail'):
            use_sendgrid = False
        else:
            # auto: Gmail SMTP が使えそうなら SendGrid より優先（dogfood 向け）
            if (
                'gmail' in smtp_server_env.lower()
                and sender_password
                and '@' in sender_email
            ):
                use_sendgrid = False
            elif sendgrid_key:
                use_sendgrid = True

        self.sendgrid_api_key = sendgrid_key if use_sendgrid else ''

        if use_sendgrid:
            # SendGrid 時はプレースホルダ SMTP_SERVER を無視（smtp.example.com 等）
            if 'sendgrid' in smtp_server_env.lower():
                self.smtp_server = smtp_server_env
            else:
                self.smtp_server = 'smtp.sendgrid.net'
            self.smtp_user = 'apikey'
            self.smtp_password = sendgrid_key
            if not self.from_email and '@' in sender_email:
                self.from_email = sender_email
        else:
            self.smtp_server = smtp_server_env
            self.smtp_user = sender_email
            self.smtp_password = sender_password
            if not self.from_email:
                self.from_email = sender_email if '@' in sender_email else ''

        # 旧コード互換（一部が sender_email / sender_password を参照しうる）
        self.sender_email = self.from_email or self.smtp_user
        self.sender_password = self.smtp_password
        self.email_provider = 'sendgrid' if use_sendgrid else 'smtp'

    def is_configured(self) -> bool:
        """送信手段と From が揃っているか。"""
        if not (self.from_email and '@' in self.from_email):
            return False
        if self.sendgrid_api_key:
            return True
        return bool(self.smtp_server and self.smtp_user and self.smtp_password)

    def send_multipart(self, to_email, subject, html_content, text_content):
        """任意の multipart メールを送信（公開 API）。"""
        return self._send_email(to_email, subject, html_content, text_content)
        
    def send_trends_summary(self, to_email, trends_data, frequency='daily'):
        """トレンドサマリーをメール送信"""
        try:
            # メール内容を作成
            subject = f"📊 トレンドサマリー - {self._get_frequency_text(frequency)}"
            html_content = self._create_html_email(trends_data, frequency)
            text_content = self._create_text_email(trends_data, frequency)
            
            # メール送信
            return self._send_email(to_email, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"メール送信エラー: {e}", exc_info=True)
            return False
    
    def _create_html_email(self, trends_data, frequency):
        """HTMLメール内容を作成"""
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        date_str = now.strftime('%Y年%m月%d日 %H:%M')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>トレンドサマリー</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ color: #333; margin: 0; }}
                .header p {{ color: #666; margin: 5px 0; }}
                .platform {{ margin-bottom: 25px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }}
                .platform-header {{ background-color: #f8f9fa; padding: 10px 15px; font-weight: bold; color: #333; }}
                .platform-content {{ padding: 15px; }}
                .trend-item {{ margin-bottom: 10px; padding: 8px; background-color: #f9f9f9; border-radius: 3px; }}
                .trend-item:last-child {{ margin-bottom: 0; }}
                .rank {{ font-weight: bold; color: #007bff; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
                .unsubscribe {{ margin-top: 15px; }}
                .unsubscribe a {{ color: #007bff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 トレンドサマリー</h1>
                    <p>{date_str} 更新</p>
                </div>
        """
        
        # 各プラットフォームのデータを追加
        for platform, data in trends_data.items():
            if data and len(data) > 0:
                platform_name = self._get_platform_name(platform)
                html += f"""
                <div class="platform">
                    <div class="platform-header">{platform_name}</div>
                    <div class="platform-content">
                """
                
                # トップ5のトレンドを表示
                for i, item in enumerate(data[:5]):
                    title = item.get('title', item.get('term', item.get('name', 'N/A')))
                    rank = i + 1
                    html += f"""
                    <div class="trend-item">
                        <span class="rank">{rank}位:</span> {title}
                    </div>
                    """
                
                html += """
                    </div>
                </div>
                """
        
        html += f"""
                <div class="footer">
                    <p>このメールは自動送信されています。</p>
                    <div class="unsubscribe">
                        <a href="#">配信を停止する</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_text_email(self, trends_data, frequency):
        """テキストメール内容を作成"""
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        date_str = now.strftime('%Y年%m月%d日 %H:%M')
        
        text = f"📊 トレンドサマリー - {date_str}\n\n"
        
        for platform, data in trends_data.items():
            if data and len(data) > 0:
                platform_name = self._get_platform_name(platform)
                text += f"【{platform_name}】\n"
                
                for i, item in enumerate(data[:5]):
                    title = item.get('title', item.get('term', item.get('name', 'N/A')))
                    rank = i + 1
                    text += f"{rank}位: {title}\n"
                
                text += "\n"
        
        text += "\nこのメールは自動送信されています。\n配信を停止する場合は、以下のリンクをクリックしてください。"
        
        return text
    
    def _get_platform_name(self, platform):
        """プラットフォーム名を日本語で取得"""
        platform_names = {
            'google': 'Google Trends',
            'youtube': 'YouTube',
            'spotify': 'Apple Music',  # 音楽トレンドはApple Music RSSを使用
            'news': 'World News',
            'podcast': 'Podcast',
            'rakuten': '楽天',
            'hatena': 'はてなブックマーク',
            'twitch': 'Twitch'
        }
        return platform_names.get(platform, platform)
    
    def _get_frequency_text(self, frequency):
        """配信頻度を日本語で取得"""
        frequency_map = {
            'daily': '毎日',
            'weekly': '毎週',
            'monthly': '毎月'
        }
        return frequency_map.get(frequency, frequency)

    def _send_via_sendgrid_api(self, to_email, subject, html_content, text_content) -> bool:
        """SendGrid Web API v3 で送信（requests 優先・urllib フォールバック）。"""
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content or " "},
                {"type": "text/html", "value": html_content or "<p></p>"},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.sendgrid_api_key}",
            "Content-Type": "application/json",
        }
        try:
            import requests

            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if 200 <= resp.status_code < 300:
                logger.info(
                    "メール送信完了 (SendGrid API): to=%s subject=%s",
                    to_email,
                    subject,
                )
                return True
            logger.error(
                "SendGrid API エラー: %s %s",
                resp.status_code,
                (resp.text or "")[:800],
            )
            return False
        except ImportError:
            pass
        except Exception as e:
            logger.error("SendGrid API (requests) 失敗: %s", e, exc_info=True)
            return False

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if 200 <= resp.status < 300:
                    logger.info(
                        "メール送信完了 (SendGrid API): to=%s subject=%s",
                        to_email,
                        subject,
                    )
                    return True
                body = resp.read()[:500]
                logger.error("SendGrid API 予期しない応答: %s %s", resp.status, body)
                return False
        except urllib.error.HTTPError as e:
            body = e.read()[:800].decode("utf-8", errors="replace")
            logger.error("SendGrid API エラー: %s %s", e.code, body)
            return False
    
    def _send_email(self, to_email, subject, html_content, text_content):
        """メール送信"""
        try:
            if not self.is_configured():
                logger.debug(
                    "メール未設定のため送信をスキップします"
                    "（SENDGRID_API_KEY + From、または SENDER_EMAIL / SENDER_PASSWORD）"
                )
                return False

            if self.sendgrid_api_key:
                return self._send_via_sendgrid_api(
                    to_email, subject, html_content, text_content
                )

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # テキストとHTMLを追加
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("メール送信完了: to=%s subject=%s", to_email, subject)
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"   ❌ SMTP認証エラー: {e}")
            logger.error(
                "      SendGrid API Key / From 認証、または Gmail アプリパスワードを確認してください",
                exc_info=True,
            )
            return False
        except smtplib.SMTPException as e:
            logger.error(f"   ❌ SMTPエラー: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"   ❌ メール送信エラー: {type(e).__name__}: {e}", exc_info=True)
            return False

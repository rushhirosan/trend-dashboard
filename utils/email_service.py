# メール送信サービス
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

class EmailService:
    def __init__(self):
        # 環境変数からメール設定を読み込む（本番環境用）
        # 環境変数が設定されていない場合はデフォルト値を使用（ローカル環境用）
        self.sender_email = os.getenv('SENDER_EMAIL', 'rushhirosan@gmail.com')
        self.sender_password = os.getenv('SENDER_PASSWORD', 'xoniafqiuwnoirce')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        
        # デバッグ情報を出力
        logger.info(f"🔍 メール設定確認:")
        logger.info(f"  SENDER_EMAIL: {self.sender_email}")
        logger.info(f"  SENDER_PASSWORD: {'*' * len(self.sender_password) if self.sender_password else 'None'}")
        logger.info(f"  SMTP_SERVER: {self.smtp_server}")
        logger.info(f"  SMTP_PORT: {self.smtp_port}")
        
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
            'spotify': 'Spotify',
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
    
    def _send_email(self, to_email, subject, html_content, text_content):
        """メール送信"""
        try:
            # メール設定確認（INFOレベルで出力）
            logger.info(f"   🔍 メール設定確認:")
            logger.info(f"      SENDER_EMAIL: {self.sender_email}")
            logger.info(f"      SENDER_PASSWORD: {'*' * len(self.sender_password) if self.sender_password else 'None'}")
            logger.info(f"      SMTP_SERVER: {self.smtp_server}")
            logger.info(f"      SMTP_PORT: {self.smtp_port}")
            
            if not self.sender_email or not self.sender_password:
                logger.error("   ❌ メール設定が不完全です - メール送信をスキップします")
                logger.error(f"   📧 送信予定メール: {to_email}")
                logger.error(f"   📧 件名: {subject}")
                return False  # エラーとしてFalseを返す
            
            # メール作成
            logger.info(f"   📝 メール内容を作成中...")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email  # 環境変数から読み込んだ送信者アドレス
            msg['To'] = to_email
            
            # テキストとHTMLを追加
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # SMTPサーバーに接続して送信
            logger.info(f"   🔌 SMTPサーバーに接続中... ({self.smtp_server}:{self.smtp_port})")
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                logger.info(f"   🔐 STARTTLSを実行中...")
                server.starttls()
                logger.info(f"   🔑 ログイン中... ({self.sender_email})")
                server.login(self.sender_email, self.sender_password)
                logger.info(f"   📤 メール送信中... ({to_email})")
                server.send_message(msg)
            
            logger.info(f"   ✅ メール送信完了: {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"   ❌ SMTP認証エラー: {e}")
            logger.error(f"      Gmailアプリパスワードが正しくない可能性があります", exc_info=True)
            return False
        except smtplib.SMTPException as e:
            logger.error(f"   ❌ SMTPエラー: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"   ❌ メール送信エラー: {type(e).__name__}: {e}", exc_info=True)
            return False

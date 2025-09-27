# メール送信サービス
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz

class EmailService:
    def __init__(self):
        # メール設定（環境変数から取得）
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        
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
            print(f"メール送信エラー: {e}")
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
            if not self.sender_email or not self.sender_password:
                print("メール設定が不完全です")
                return False
            
            # メール作成
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_email
            
            # テキストとHTMLを追加
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # SMTPサーバーに接続して送信
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"メール送信完了: {to_email}")
            return True
            
        except Exception as e:
            print(f"メール送信エラー: {e}")
            return False

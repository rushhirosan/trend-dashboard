"""
サブスクリプション管理クラス
メール配信の登録・解除・管理を行う
"""

import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from database_config import TrendsCache


class SubscriptionManager:
    """サブスクリプション管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.db = TrendsCache()
        self._ensure_subscription_table()
    
    def _ensure_subscription_table(self):
        """サブスクリプションテーブルの存在確認と作成"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # サブスクリプションテーブルを作成
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS subscriptions (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
                            categories TEXT[],  -- 配信するカテゴリの配列
                            is_active BOOLEAN DEFAULT TRUE,
                            unsubscribe_token VARCHAR(255) UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # インデックスを作成
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(email)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(is_active)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_token ON subscriptions(unsubscribe_token)')
                    
                    conn.commit()
                    print("✅ サブスクリプションテーブル確認完了")
                    
        except Exception as e:
            print(f"❌ サブスクリプションテーブル作成エラー: {e}")
            raise
    
    def validate_email(self, email: str) -> bool:
        """メールアドレスの形式チェック"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def subscribe(self, email: str, frequency: str = 'daily', categories: List[str] = None) -> Tuple[bool, str]:
        """
        サブスクリプション登録
        
        Args:
            email: メールアドレス
            frequency: 配信頻度 (daily, weekly, monthly)
            categories: 配信するカテゴリのリスト
            
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            # メールアドレス形式チェック
            if not self.validate_email(email):
                return False, "有効なメールアドレスを入力してください"
            
            # 配信頻度チェック
            if frequency not in ['daily', 'weekly', 'monthly']:
                return False, "配信頻度が無効です"
            
            # デフォルトカテゴリ設定
            if categories is None:
                categories = [
                    'google_trends', 'youtube_trends', 'music_trends', 
                    'news_trends', 'podcast_trends', 'rakuten_trends',
                    'hatena_trends', 'twitch_trends'
                ]
            
            # 登録解除トークン生成
            unsubscribe_token = str(uuid.uuid4())
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO subscriptions (email, frequency, categories, is_active, unsubscribe_token)
                        VALUES (%s, %s, %s, TRUE, %s)
                        ON CONFLICT (email) DO UPDATE SET
                            frequency = EXCLUDED.frequency,
                            categories = EXCLUDED.categories,
                            is_active = TRUE,
                            unsubscribe_token = EXCLUDED.unsubscribe_token,
                            updated_at = CURRENT_TIMESTAMP
                    """, (email, frequency, categories, unsubscribe_token))
                    conn.commit()
            
            print(f"📧 サブスクリプション登録完了: {email} ({frequency})")
            return True, "サブスクリプション登録が完了しました"
            
        except Exception as e:
            print(f"❌ サブスクリプション登録エラー: {e}")
            return False, "登録に失敗しました"
    
    def unsubscribe(self, email: str = None, token: str = None) -> Tuple[bool, str]:
        """
        サブスクリプション登録解除
        
        Args:
            email: メールアドレス（emailまたはtokenのどちらかが必要）
            token: 登録解除トークン
            
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            if not email and not token:
                return False, "メールアドレスまたはトークンが必要です"
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    if email:
                        cursor.execute("""
                            UPDATE subscriptions 
                            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                            WHERE email = %s
                        """, (email,))
                    else:
                        cursor.execute("""
                            UPDATE subscriptions 
                            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                            WHERE unsubscribe_token = %s
                        """, (token,))
                    
                    affected_rows = cursor.rowcount
                    conn.commit()
            
            if affected_rows > 0:
                print(f"📧 サブスクリプション登録解除完了: {email or token}")
                return True, "サブスクリプションを解除しました"
            else:
                return False, "サブスクリプションが見つかりません"
                
        except Exception as e:
            print(f"❌ サブスクリプション登録解除エラー: {e}")
            return False, "解除に失敗しました"
    
    def get_subscription_status(self, email: str) -> Optional[Dict]:
        """
        サブスクリプション状態を取得
        
        Args:
            email: メールアドレス
            
        Returns:
            サブスクリプション情報の辞書、またはNone
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT email, frequency, categories, is_active, created_at, updated_at
                        FROM subscriptions
                        WHERE email = %s AND is_active = TRUE
                    """, (email,))
                    result = cursor.fetchone()
                    
                    if result:
                        return {
                            'email': result[0],
                            'frequency': result[1],
                            'categories': result[2],
                            'is_active': result[3],
                            'created_at': result[4],
                            'updated_at': result[5]
                        }
                    return None
                    
        except Exception as e:
            print(f"❌ サブスクリプション状態取得エラー: {e}")
            return None
    
    def get_all_active_subscriptions(self) -> List[Dict]:
        """
        アクティブなサブスクリプション一覧を取得
        
        Returns:
            サブスクリプション情報のリスト
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT email, frequency, categories, created_at, updated_at
                        FROM subscriptions
                        WHERE is_active = TRUE
                        ORDER BY created_at DESC
                    """)
                    results = cursor.fetchall()
                    
                    subscriptions = []
                    for row in results:
                        subscriptions.append({
                            'email': row[0],
                            'frequency': row[1],
                            'categories': row[2],
                            'created_at': row[3],
                            'updated_at': row[4]
                        })
                    
                    return subscriptions
                    
        except Exception as e:
            print(f"❌ サブスクリプション一覧取得エラー: {e}")
            return []
    
    def get_subscriptions_by_frequency(self, frequency: str) -> List[Dict]:
        """
        指定された配信頻度のサブスクリプション一覧を取得
        
        Args:
            frequency: 配信頻度 (daily, weekly, monthly)
            
        Returns:
            サブスクリプション情報のリスト
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT email, frequency, categories, created_at, updated_at
                        FROM subscriptions
                        WHERE is_active = TRUE AND frequency = %s
                        ORDER BY created_at DESC
                    """, (frequency,))
                    results = cursor.fetchall()
                    
                    subscriptions = []
                    for row in results:
                        subscriptions.append({
                            'email': row[0],
                            'frequency': row[1],
                            'categories': row[2],
                            'created_at': row[3],
                            'updated_at': row[4]
                        })
                    
                    return subscriptions
                    
        except Exception as e:
            print(f"❌ 配信頻度別サブスクリプション取得エラー: {e}")
            return []
    
    def update_subscription(self, email: str, frequency: str = None, categories: List[str] = None) -> Tuple[bool, str]:
        """
        サブスクリプション情報を更新
        
        Args:
            email: メールアドレス
            frequency: 新しい配信頻度
            categories: 新しい配信カテゴリ
            
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            if not frequency and not categories:
                return False, "更新する情報が指定されていません"
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 動的にUPDATE文を構築
                    update_fields = []
                    params = []
                    
                    if frequency:
                        update_fields.append("frequency = %s")
                        params.append(frequency)
                    
                    if categories:
                        update_fields.append("categories = %s")
                        params.append(categories)
                    
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(email)
                    
                    query = f"""
                        UPDATE subscriptions 
                        SET {', '.join(update_fields)}
                        WHERE email = %s AND is_active = TRUE
                    """
                    
                    cursor.execute(query, params)
                    affected_rows = cursor.rowcount
                    conn.commit()
            
            if affected_rows > 0:
                print(f"📧 サブスクリプション更新完了: {email}")
                return True, "サブスクリプション情報を更新しました"
            else:
                return False, "サブスクリプションが見つかりません"
                
        except Exception as e:
            print(f"❌ サブスクリプション更新エラー: {e}")
            return False, "更新に失敗しました"
    
    def get_statistics(self) -> Dict:
        """
        サブスクリプション統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 総登録数
                    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active = TRUE")
                    total_active = cursor.fetchone()[0]
                    
                    # 配信頻度別統計
                    cursor.execute("""
                        SELECT frequency, COUNT(*) 
                        FROM subscriptions 
                        WHERE is_active = TRUE 
                        GROUP BY frequency
                    """)
                    frequency_stats = dict(cursor.fetchall())
                    
                    # 最近の登録数（過去30日）
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM subscriptions 
                        WHERE is_active = TRUE 
                        AND created_at >= NOW() - INTERVAL '30 days'
                    """)
                    recent_registrations = cursor.fetchone()[0]
                    
                    return {
                        'total_active': total_active,
                        'frequency_stats': frequency_stats,
                        'recent_registrations': recent_registrations
                    }
                    
        except Exception as e:
            print(f"❌ サブスクリプション統計取得エラー: {e}")
            return {
                'total_active': 0,
                'frequency_stats': {},
                'recent_registrations': 0
            }


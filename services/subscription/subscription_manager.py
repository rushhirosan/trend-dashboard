"""
サブスクリプション管理クラス
メール配信の登録・解除・管理を行う
"""

import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from database_config import TrendsCache
from utils.email_service import EmailService
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)


class SubscriptionManager:
    """サブスクリプション管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.db = TrendsCache()
        self.email_service = EmailService()
        self._ensure_subscription_table()
    
    def _ensure_subscription_table(self):
        """サブスクリプションテーブルの存在確認と作成"""
        try:
            try:
                conn = self.db.get_connection()
                if not conn:
                    logger.warning("⚠️ データベース接続が利用できません。テーブル作成をスキップします")
                    return
            except Exception as e:
                logger.warning(f"⚠️ サブスクリプションテーブル作成をスキップします: データベース接続エラー ({e})")
                return
            
            with conn:
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
                    logger.info("✅ サブスクリプションテーブル確認完了")
                    
        except Exception as e:
            logger.warning(f"⚠️ サブスクリプションテーブル作成エラー: {e}")
            # 起動時のエラーは例外を再スローせず、ログのみ出力
            pass
    
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
            if categories is None or len(categories) == 0:
                # サブスクリプションページと同じ順序（JP/US含む）
                categories = self._get_category_order()
            
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
            
            # 登録確認メールを送信
            self._send_confirmation_email(email, frequency, categories, unsubscribe_token)
            
            logger.info(f"📧 サブスクリプション登録完了: {email} ({frequency})")
            return True, "サブスクリプション登録が完了しました。確認メールを送信しました。"
            
        except Exception as e:
            logger.error(f"❌ サブスクリプション登録エラー: {e}", exc_info=True)
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
                logger.info(f"📧 サブスクリプション登録解除完了: {email or token}")
                return True, "サブスクリプションを解除しました"
            else:
                return False, "サブスクリプションが見つかりません"
                
        except Exception as e:
            logger.error(f"❌ サブスクリプション登録解除エラー: {e}", exc_info=True)
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
            logger.error(f"❌ サブスクリプション状態取得エラー: {e}", exc_info=True)
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
                    # テーブル構造を確認して適切なカラム名を使用
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'subscriptions' 
                        AND column_name IN ('created_at', 'subscribed_at')
                    """)
                    date_columns = [row[0] for row in cursor.fetchall()]
                    date_column = date_columns[0] if date_columns else 'updated_at'
                    
                    cursor.execute(f"""
                        SELECT email, frequency, categories, {date_column}, updated_at
                        FROM subscriptions
                        WHERE is_active = TRUE
                        ORDER BY {date_column} DESC
                    """)
                    results = cursor.fetchall()
                    
                    subscriptions = []
                    for row in results:
                        subscriptions.append({
                            'email': row[0],
                            'frequency': row[1],
                            'categories': row[2],
                            'created_at': row[3] if len(row) > 3 else None,
                            'updated_at': row[4] if len(row) > 4 else None
                        })
                    
                    return subscriptions
                    
        except Exception as e:
            logger.error(f"❌ サブスクリプション一覧取得エラー: {e}", exc_info=True)
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
            logger.error(f"❌ 配信頻度別サブスクリプション取得エラー: {e}", exc_info=True)
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
                logger.info(f"📧 サブスクリプション更新完了: {email}")
                return True, "サブスクリプション情報を更新しました"
            else:
                return False, "サブスクリプションが見つかりません"
                
        except Exception as e:
            logger.error(f"❌ サブスクリプション更新エラー: {e}", exc_info=True)
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
            logger.error(f"❌ サブスクリプション統計取得エラー: {e}", exc_info=True)
            return {
                'total_active': 0,
                'frequency_stats': {},
                'recent_registrations': 0
            }
    
    def send_trends_summary(self):
        """トレンドサマリー配信を実行"""
        import psycopg2
        
        try:
            logger.info("=" * 60)
            logger.info("📧 トレンドサマリー配信開始")
            logger.info("=" * 60)
            
            # アクティブなサブスクリプションを取得
            logger.info("🔍 アクティブなサブスクリプションを取得中...")
            try:
                active_subscriptions = self._get_active_subscriptions()
                logger.info(f"📊 取得結果: {len(active_subscriptions)}件のアクティブなサブスクリプション")
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                # データベース接続エラーの場合、メール送信をスキップ
                logger.error("=" * 60)
                logger.error("❌ データベース接続エラーのため、メール送信をスキップします")
                logger.error(f"   エラー詳細: {type(e).__name__}: {e}")
                logger.error("=" * 60)
                # エラーを再スローして、上位のエラーハンドリングで処理
                raise
            except Exception as e:
                # その他のエラーも再スロー
                logger.error(f"❌ サブスクリプション取得エラー: {e}", exc_info=True)
                raise
            
            if not active_subscriptions:
                logger.info("ℹ️ アクティブなサブスクリプションがありません（正常）")
                logger.info("   メール送信はスキップされます")
                logger.info("=" * 60)
                return
            
            # 各サブスクリプションの情報を表示
            for i, sub in enumerate(active_subscriptions, 1):
                logger.info(f"   {i}. {sub['email']} ({sub['frequency']})")
                logger.info(f"      カテゴリ: {sub.get('categories', [])}")
            
            # メモリ効率化: 全サブスクリプションで必要なカテゴリを収集し、一度だけデータ取得
            all_categories = set()
            for subscription in active_subscriptions:
                categories = subscription.get('categories', [])
                if categories:
                    all_categories.update(categories)
                else:
                    # カテゴリが指定されていない場合は全カテゴリが必要
                    all_categories = None
                    break
            
            # 一度だけデータ取得（メモリ節約）
            logger.info(f"🔍 全サブスクリプション用のトレンドデータを取得中... (カテゴリ数: {len(all_categories) if all_categories else '全カテゴリ'})")
            shared_trends_data = self._get_all_trends_data(categories=list(all_categories) if all_categories else None)
            logger.info(f"📊 トレンドデータ取得完了: {len(shared_trends_data)}カテゴリ")
            
            # 各サブスクリプションにメール送信
            success_count = 0
            fail_count = 0
            
            for i, subscription in enumerate(active_subscriptions, 1):
                email = subscription['email']
                logger.info(f"[{i}/{len(active_subscriptions)}] 📧 {email} にメール送信中...")
                
                # 共有データから、このサブスクリプションに必要なカテゴリのみを抽出
                categories = subscription.get('categories', [])
                if categories:
                    # 指定されたカテゴリのみを抽出
                    filtered_trends_data = {}
                    for cat in categories:
                        # カテゴリ名のマッチング（_jpや_us付きも考慮）
                        matched = False
                        for key in shared_trends_data.keys():
                            if cat == key or key.startswith(cat + '_'):
                                filtered_trends_data[key] = shared_trends_data[key]
                                matched = True
                                break
                        if not matched:
                            # 正規化してマッチング
                            normalized_cat = cat.rsplit('_', 1)[0] if cat.endswith('_jp') or cat.endswith('_us') else cat
                            for key in shared_trends_data.keys():
                                normalized_key = key.rsplit('_', 1)[0] if key.endswith('_jp') or key.endswith('_us') else key
                                if normalized_cat == normalized_key:
                                    filtered_trends_data[key] = shared_trends_data[key]
                                    break
                    trends_data = filtered_trends_data if filtered_trends_data else shared_trends_data
                else:
                    # カテゴリが指定されていない場合は全データを使用
                    trends_data = shared_trends_data
                
                logger.info(f"📊 {email} 用データ: {len(trends_data)}カテゴリ")
                
                try:
                    self._send_trends_summary_email(subscription, trends_data)
                    success_count += 1
                    logger.info(f"   ✅ メール送信成功: {email}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"   ❌ メール送信失敗: {email} - {e}", exc_info=True)
            
            logger.info("=" * 60)
            logger.info(f"📧 トレンドサマリー配信完了")
            logger.info(f"   ✅ 成功: {success_count}件")
            if fail_count > 0:
                logger.warning(f"   ❌ 失敗: {fail_count}件")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ トレンドサマリー配信エラー: {e}", exc_info=True)
            logger.error("=" * 60)
    
    def _get_active_subscriptions(self):
        """アクティブなサブスクリプションを取得（接続エラー時はリトライ）
        
        Returns:
            list: アクティブなサブスクリプションのリスト。エラーが発生した場合は例外を再スローする。
        
        Raises:
            psycopg2.InterfaceError: データベース接続エラー（リトライ後も失敗）
            psycopg2.OperationalError: データベース操作エラー（リトライ後も失敗）
            Exception: その他の予期しないエラー
        """
        import psycopg2
        import time
        
        max_retries = 3
        retry_delay = 1.0  # 1秒
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 接続を強制的にリセット（接続が閉じられている場合に備えて）
                if attempt > 0:
                    logger.info(f"🔄 サブスクリプション取得をリトライします（試行 {attempt + 1}/{max_retries}）")
                    # 接続をリセット
                    if hasattr(self.db, 'connection'):
                        self.db.connection = None
                    time.sleep(retry_delay)
                
                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM subscriptions")
                        total_count = cursor.fetchone()[0]
                        
                        # アクティブなサブスクリプションのみを取得
                        cursor.execute("""
                            SELECT email, frequency, categories, unsubscribe_token 
                            FROM subscriptions 
                            WHERE is_active = true
                        """)
                        results = cursor.fetchall()
                        
                        subscriptions = []
                        for row in results:
                            subscriptions.append({
                                'email': row[0],
                                'frequency': row[1],
                                'categories': row[2] if row[2] else [],
                                'unsubscribe_token': row[3] if len(row) > 3 else None
                            })
                        
                        logger.info(f"   ✅ データベースから{len(subscriptions)}件のアクティブなサブスクリプションを取得（全{total_count}件中）")
                        
                        return subscriptions
                        
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                # 接続エラーの場合はリトライ
                last_error = e
                logger.warning(f"⚠️ データベース接続エラー（試行 {attempt + 1}/{max_retries}）: {e}")
                if attempt < max_retries - 1:
                    # 接続をリセットして再試行
                    if hasattr(self.db, 'connection'):
                        self.db.connection = None
                    continue
                else:
                    # 全てのリトライが失敗した場合、エラーを再スロー
                    logger.error("=" * 60)
                    logger.error(f"❌ アクティブサブスクリプション取得に失敗しました（最大試行回数: {max_retries}回）")
                    logger.error(f"   エラー: {type(e).__name__}: {e}")
                    logger.error("   データベース接続が確立できないため、メール送信をスキップします")
                    logger.error("   データベースサーバーの状態を確認してください")
                    logger.error("=" * 60)
                    # エラーを再スローして、上位で処理させる
                    raise
            except Exception as e:
                # 接続エラー以外のエラーも再スロー
                logger.error("=" * 60)
                logger.error(f"❌ アクティブサブスクリプション取得エラー: {type(e).__name__}: {e}")
                logger.error("=" * 60)
                raise
        
        # 通常はここには到達しないが、念のため
        if last_error:
            raise last_error
        raise Exception("アクティブサブスクリプション取得に失敗しました（不明なエラー）")
    
    def _get_all_trends_data(self, categories=None):
        """選択されたカテゴリのトレンドデータを取得
        
        Args:
            categories: 選択されたカテゴリのリスト（Noneの場合は全カテゴリ）
        """
        try:
            # カテゴリが指定されていない場合、または空のリストの場合は全カテゴリを取得
            if not categories or len(categories) == 0:
                logger.info(f"📊 カテゴリが指定されていないため、全カテゴリを取得します")
                categories = self._get_category_order()
            
            logger.info(f"📊 データ取得対象カテゴリ: {categories} (合計{len(categories)}件)")
            
            # カテゴリを正規化して、必要なデータを判断
            needed_normalized_categories = set()
            category_to_params = {}  # カテゴリ名 -> (normalized_category, region, params)
            
            def normalize_category(cat):
                """カテゴリ名を正規化（google_trends_jp -> google_trends）"""
                if cat.endswith('_jp') or cat.endswith('_us'):
                    return cat.rsplit('_', 1)[0]
                return cat
            
            for cat in categories:
                normalized = normalize_category(cat)
                needed_normalized_categories.add(normalized)
                
                # リージョンとパラメータを決定
                if cat.endswith('_jp'):
                    region = 'JP'
                    country = 'jp'
                elif cat.endswith('_us'):
                    region = 'US'
                    country = 'us'
                else:
                    region = 'JP'
                    country = 'jp'
                
                category_to_params[cat] = (normalized, region, country)
            # 各カテゴリのマネージャーをインポート
            from services.trends.google_trends import GoogleTrendsManager
            from services.trends.youtube_trends import YouTubeTrendsManager
            from services.trends.music_trends import MusicTrendsManager
            from services.trends.news_trends import NewsTrendsManager
            from services.trends.worldnews_trends import WorldNewsTrendsManager
            from services.trends.podcast_trends import PodcastTrendsManager
            from services.trends.rakuten_trends import RakutenTrendsManager
            from services.trends.hatena_trends import HatenaTrendsManager
            from services.trends.twitch_trends import TwitchTrendsManager
            from services.trends.cnn_trends import CNNTrendsManager
            from services.trends.producthunt_trends import ProductHuntTrendsManager
            from services.trends.nhk_trends import NHKTrendsManager
            from services.trends.qiita_trends import QiitaTrendsManager
            from services.trends.reddit_trends import RedditTrendsManager
            from services.trends.hackernews_trends import HackerNewsTrendsManager
            from services.trends.stock_trends import StockTrendsManager
            from services.trends.crypto_trends import CryptoTrendsManager
            from services.trends.movie_trends import MovieTrendsManager
            from services.trends.book_trends import BookTrendsManager
            from services.trends.github_trends import GitHubTrendsManager
            from services.trends.appstore_trends import AppStoreTrendsManager
            from services.trends.cisa_kev_trends import CISAKEVTrendsManager
            from services.trends.thehackernews_trends import TheHackerNewsTrendsManager
            from services.trends.devto_trends import DevToTrendsManager
            from services.trends.medium_trends import MediumTrendsManager
            from services.trends.ebay_trends import eBayTrendsManager
            # 各マネージャーのインスタンスを作成
            managers = {
                'google_trends': GoogleTrendsManager(),
                'youtube_trends': YouTubeTrendsManager(),
                'music_trends': MusicTrendsManager(),
                'news_trends': WorldNewsTrendsManager(),  # news_trends_jpはWorld News APIの日本版データを使用
                'worldnews_trends': WorldNewsTrendsManager(),
                'podcast_trends': PodcastTrendsManager(),
                'rakuten_trends': RakutenTrendsManager(),
                'hatena_trends': HatenaTrendsManager(),
                'twitch_trends': TwitchTrendsManager(),
                'cnn_trends': CNNTrendsManager(),
                'producthunt_trends': ProductHuntTrendsManager(),
                'nhk_trends': NHKTrendsManager(),
                'qiita_trends': QiitaTrendsManager(),
                'reddit_trends': RedditTrendsManager(),
                'hackernews_trends': HackerNewsTrendsManager(),
                'stock_trends': StockTrendsManager(),
                'crypto_trends': CryptoTrendsManager(),
                'movie_trends': MovieTrendsManager(),
                'book_trends': BookTrendsManager(),
                'github_trends': GitHubTrendsManager(),
                'appstore_trends': AppStoreTrendsManager(),
                'cisa_kev_trends': CISAKEVTrendsManager(),
                'thehackernews_trends': TheHackerNewsTrendsManager(),
                'devto_trends': DevToTrendsManager(),
                'medium_trends': MediumTrendsManager(),
                'ebay_trends': eBayTrendsManager(),
            }
            
            trends_data = {}
            
            # 選択されたカテゴリのデータを取得
            for original_cat in categories:
                normalized_cat, region, country = category_to_params[original_cat]
                
                if normalized_cat not in managers:
                    logger.warning(f"⚠️ マネージャーが見つかりません: {normalized_cat}")
                    continue
                
                manager = managers[normalized_cat]
                try:
                    logger.debug(f"📊 {original_cat} ({normalized_cat}, region={region}) データ取得中...")
                    
                    if normalized_cat == 'google_trends':
                        result = manager.get_trends(region=region)
                    elif normalized_cat == 'youtube_trends':
                        result = manager.get_trends(region_code=region)
                    elif normalized_cat == 'music_trends':
                        result = manager.get_trends(service='spotify', region=region)
                    elif normalized_cat == 'worldnews_trends':
                        result = manager.get_trends(country=country, force_refresh=False)
                    elif normalized_cat == 'news_trends':
                        # news_trends_jpはWorld News APIの日本版データを使用
                        result = manager.get_trends(country=country, force_refresh=False)
                    elif normalized_cat == 'podcast_trends':
                        result = manager.get_trends(trend_type='best_podcasts', region=country, force_refresh=False)
                    elif normalized_cat == 'rakuten_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'hatena_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'twitch_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'cnn_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'producthunt_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'nhk_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'qiita_trends':
                        result = manager.get_trends(force_refresh=False)
                    elif normalized_cat == 'reddit_trends':
                        result = manager.get_trends('all', limit=25, time_filter='day', force_refresh=False)
                    elif normalized_cat == 'hackernews_trends':
                        result = manager.get_trends('top', limit=25, force_refresh=False)
                    elif normalized_cat == 'stock_trends':
                        # 株価: marketパラメータでJP/USを指定
                        market = 'JP' if region == 'JP' else 'US'
                        result = manager.get_trends(market=market, limit=25, force_refresh=False)
                    elif normalized_cat == 'crypto_trends':
                        # 仮想通貨: リージョンに関係なく同じデータ
                        result = manager.get_trends(limit=25, force_refresh=False)
                    elif normalized_cat == 'movie_trends':
                        # 映画: countryパラメータでJP/USを指定
                        result = manager.get_trends(country=region, time_window='day', limit=25, force_refresh=False)
                    elif normalized_cat == 'book_trends':
                        # 本: countryパラメータでJP/USを指定
                        result = manager.get_trends(country=region, limit=25, force_refresh=False)
                    elif normalized_cat == 'github_trends':
                        # GitHub: リージョンに関係なく同じデータ
                        result = manager.get_trends(language='all', limit=25, force_refresh=False)
                    elif normalized_cat == 'appstore_trends':
                        # App Store: countryパラメータでJP/USを指定
                        result = manager.get_trends(country=region, category='all', limit=25, force_refresh=False)
                    elif normalized_cat == 'cisa_kev_trends':
                        result = manager.get_trends(limit=25, force_refresh=False)
                    elif normalized_cat == 'thehackernews_trends':
                        result = manager.get_trends(limit=25, force_refresh=False)
                    elif normalized_cat == 'devto_trends':
                        result = manager.get_trends(limit=25, force_refresh=False)
                    elif normalized_cat == 'medium_trends':
                        result = manager.get_trends(limit=25, force_refresh=False)
                    elif normalized_cat == 'ebay_trends':
                        result = manager.get_trends(category='fashion', limit=25, force_refresh=False)
                    else:
                        logger.warning(f"   ⚠️ {original_cat}: 未対応のカテゴリです")
                        result = None
                    
                    # resultがNoneの場合はスキップ
                    if result is None:
                        logger.warning(f"   ⚠️ {original_cat}: マネージャーがNoneを返しました")
                        trends_data[original_cat] = {
                            'data': [],
                            'status': 'no_manager',
                            'source': 'unknown'
                        }
                        continue
                    
                    # エラーチェック: resultに'error'キーがある場合はスキップ
                    if result and 'error' in result:
                        logger.warning(f"   ⚠️ {original_cat}: エラーが返されました - {result.get('error')}")
                        trends_data[original_cat] = {
                            'data': [],
                            'status': 'error',
                            'source': 'error',
                            'error': result.get('error')
                        }
                        continue
                    
                    # データ構造に応じて処理
                    data_list = None
                    if result and result.get('data'):
                        if isinstance(result['data'], dict) and 'data' in result['data']:
                            # ネストされた構造の場合
                            data_list = result['data']['data']
                        elif isinstance(result['data'], list):
                            # 直接リストの場合
                            data_list = result['data']
                    
                    if data_list and len(data_list) > 0:
                        # 元のカテゴリ名（_jpや_us付き）をキーとして使用
                        trends_data[original_cat] = {
                            'data': data_list[:5],  # 上位5件のみ
                            'status': result.get('status', 'unknown'),
                            'source': result.get('source', 'unknown')
                        }
                        logger.info(f"   ✅ {original_cat}: {len(data_list[:5])}件のデータを取得")
                    else:
                        trends_data[original_cat] = {
                            'data': [],
                            'status': 'no_data',
                            'source': 'unknown'
                        }
                        logger.warning(f"   ⚠️ {original_cat}: データなし (result={result})")
                        
                except Exception as e:
                    logger.error(f"❌ {original_cat} データ取得エラー: {e}", exc_info=True)
                    trends_data[original_cat] = {
                        'data': [],
                        'status': 'error',
                        'source': 'error'
                    }
            
            logger.info(f"📊 トレンドデータ取得結果: {len(trends_data)}カテゴリ, データあり: {sum(1 for v in trends_data.values() if v.get('data'))}カテゴリ")
            return trends_data
            
        except Exception as e:
            logger.error(f"❌ トレンドデータ取得エラー: {e}", exc_info=True)
            return {}
    
    def _send_trends_summary_email(self, subscription, trends_data):
        """トレンドサマリー配信メールを送信"""
        try:
            email = subscription['email']
            categories = subscription.get('categories', [])
            unsubscribe_token = subscription.get('unsubscribe_token')
            
            # categoriesが空の場合は、trends_dataのキー（実際に取得されたカテゴリ）を使用
            if not categories or len(categories) == 0:
                logger.info(f"📊 {email}: カテゴリが指定されていないため、取得された全カテゴリを使用します")
                categories = list(trends_data.keys())
            else:
                # categoriesに含まれるカテゴリ名を、trends_dataのキー形式に変換
                # 例: 'worldnews_trends' -> 'worldnews_trends_us' または 'worldnews_trends_jp'
                # trends_dataのキーと一致するものを探す
                logger.info(f"📊 {email}: カテゴリマッチング開始 - サブスクリプションカテゴリ: {categories}")
                logger.info(f"📊 {email}: trends_dataのキー: {list(trends_data.keys())}")
                matched_categories = []
                for cat in categories:
                    logger.debug(f"   🔍 マッチング中: {cat}")
                    # まず完全一致を確認
                    if cat in trends_data:
                        matched_categories.append(cat)
                        logger.debug(f"      ✅ 完全一致: {cat}")
                    else:
                        # _jpや_usを付けて探す
                        found = False
                        for suffix in ['_jp', '_us']:
                            cat_with_suffix = cat + suffix
                            if cat_with_suffix in trends_data:
                                matched_categories.append(cat_with_suffix)
                                logger.debug(f"      ✅ サフィックス追加で一致: {cat} -> {cat_with_suffix}")
                                found = True
                                break
                        
                        if not found:
                            # 一致しない場合は、trends_dataのキーから正規化して探す
                            normalized_cat = cat.rsplit('_', 1)[0] if cat.endswith('_jp') or cat.endswith('_us') else cat
                            logger.debug(f"      🔍 正規化: {cat} -> {normalized_cat}")
                            for trend_key in trends_data.keys():
                                normalized_trend_key = trend_key.rsplit('_', 1)[0] if trend_key.endswith('_jp') or trend_key.endswith('_us') else trend_key
                                if normalized_cat == normalized_trend_key:
                                    matched_categories.append(trend_key)
                                    logger.debug(f"      ✅ 正規化で一致: {normalized_cat} -> {trend_key}")
                                    found = True
                                    break
                        
                        if not found:
                            logger.warning(f"      ⚠️ マッチング失敗: {cat} (trends_dataに該当するキーが見つかりませんでした)")
                
                categories = matched_categories if matched_categories else list(trends_data.keys())
                logger.info(f"📊 {email}: カテゴリマッチング結果: {len(categories)}カテゴリ ({categories[:5]}...)")
            
            # メール内容を作成
            subject = "📊 トレンドサマリー配信 - " + datetime.now().strftime('%Y年%m月%d日')
            html_content = self._create_trends_summary_html(trends_data, categories, unsubscribe_token)
            text_content = self._create_trends_summary_text(trends_data, categories, unsubscribe_token)
            
            # メール送信
            success = self.email_service._send_email(email, subject, html_content, text_content)
            
            if success:
                logger.info(f"✅ トレンドサマリー配信完了: {email}")
            else:
                logger.error(f"❌ トレンドサマリー配信失敗: {email} - メール送信がFalseを返しました")
                raise Exception(f"メール送信が失敗しました: {email}")
                
        except Exception as e:
            logger.error(f"❌ トレンドサマリー配信エラー: {e}", exc_info=True)
            raise  # 例外を再発生させて、呼び出し元でエラーとして処理されるようにする

    def _send_confirmation_email(self, email: str, frequency: str, categories: List[str], unsubscribe_token: str):
        """登録確認メールを送信"""
        try:
            # メール内容を作成
            subject = "📧 トレンドサマリー配信のご登録ありがとうございます"
            html_content = self._create_confirmation_html(email, frequency, categories, unsubscribe_token)
            text_content = self._create_confirmation_text(email, frequency, categories, unsubscribe_token)
            
            # メール送信
            success = self.email_service._send_email(email, subject, html_content, text_content)
            
            if success:
                logger.info(f"✅ 確認メール送信完了: {email}")
            else:
                logger.warning(f"⚠️ 確認メール送信失敗: {email}")
                
        except Exception as e:
            logger.error(f"❌ 確認メール送信エラー: {e}", exc_info=True)
    
    def _get_category_order(self):
        """サブスクリプションページと同じ順序でカテゴリを定義（トレンドページの順序に合わせる）"""
        return [
            # 日本のトレンド（トレンドページの順序通り）
            # 1. NHK ニュース
            'nhk_trends_jp',
            # 2. ニューストレンド (World News)
            'news_trends_jp',
            # 3. Google Trends
            'google_trends_jp',
            # 4. YouTube トレンド
            'youtube_trends_jp',
            # 5. はてなブックマークトレンド
            'hatena_trends_jp',
            # 6. Qiita トレンド
            'qiita_trends_jp',
            # 7. 株価トレンド
            'stock_trends_jp',
            # 8. 仮想通貨トレンド
            'crypto_trends_jp',
            # 9. 音楽トレンド (Spotify)
            'music_trends_jp',
            # 10. ポッドキャストトレンド
            'podcast_trends_jp',
            # 11. 映画トレンド
            'movie_trends_jp',
            # 12. 本トレンド
            'book_trends_jp',
            # 13. GitHub
            'github_trends_jp',
            # 14. App Store
            'appstore_trends_jp',
            # 15. 楽天商品トレンド
            'rakuten_trends_jp',
            # 16. Twitchゲームトレンド
            'twitch_trends_jp',
            # USのトレンド（トレンドページの順序通り）
            # 1. CNN News
            'cnn_trends_us',
            # 2. World News
            'worldnews_trends_us',
            # 3. Google Trends
            'google_trends_us',
            # 4. YouTube トレンド
            'youtube_trends_us',
            # 5. Hacker News
            'hackernews_trends_us',
            # 6. Product Hunt
            'producthunt_trends_us',
            # 7. DEV.to
            'devto_trends_us',
            # 8. Medium
            'medium_trends_us',
            # 9. CISA KEV
            'cisa_kev_trends_us',
            # 10. The Hacker News
            'thehackernews_trends_us',
            # 11. GitHub (US)
            'github_trends_us',
            # 12. App Store (US)
            'appstore_trends_us',
            # 13. Stock Trends
            'stock_trends_us',
            # 14. Cryptocurrency Trends
            'crypto_trends_us',
            # 15. 映画トレンド (US)
            'movie_trends_us',
            # 16. 本トレンド (US)
            'book_trends_us',
            # 17. 音楽トレンド (Spotify)
            'music_trends_us',
            # 18. ポッドキャストトレンド
            'podcast_trends_us',
            # 19. eBay Popular/Trending
            'ebay_trends_us',
            # 20. Twitchゲームトレンド
            'twitch_trends_us',
        ]
    
    def _sort_categories_by_order(self, categories):
        """カテゴリをサブスクリプションページの順序でソート"""
        order = self._get_category_order()
        # カテゴリを順序に従ってソート
        category_order_map = {cat: idx for idx, cat in enumerate(order)}
        
        def get_sort_key(cat):
            # _jpや_usで終わるカテゴリの順序を取得
            if cat in category_order_map:
                return category_order_map[cat]
            # 見つからない場合は最後に配置
            return len(order) + hash(cat)
        
        return sorted(categories, key=get_sort_key)
    
    def _create_trends_summary_html(self, trends_data, categories, unsubscribe_token=None):
        """トレンドサマリー配信メールのHTML内容を作成
        
        Args:
            trends_data: トレンドデータの辞書
            categories: カテゴリのリスト
            unsubscribe_token: 登録解除トークン（オプション）
        """
        try:
            # カテゴリをサブスクリプションページの順序でソート
            categories = self._sort_categories_by_order(categories)
            
            # 配信停止URLを生成
            if unsubscribe_token:
                unsubscribe_url = f"https://trends-dashboard.fly.dev/subscription/unsubscribe/{unsubscribe_token}"
            else:
                unsubscribe_url = "https://trends-dashboard.fly.dev/subscription/"
            
            html = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <title>トレンドサマリー配信</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .category {{ margin-bottom: 30px; border: 1px solid #ddd; border-radius: 5px; }}
                    .category-title {{ background-color: #007bff; color: white; padding: 10px; font-weight: bold; }}
                    .category-content {{ padding: 15px; }}
                    .trend-item {{ margin-bottom: 10px; padding: 8px; background-color: #f8f9fa; border-radius: 3px; }}
                    .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📊 トレンドサマリー配信</h1>
                    <p>{datetime.now().strftime('%Y年%m月%d日')}</p>
                </div>
                
                <div class="content">
                    <p>こんにちは！本日の<a href="https://trends-dashboard.fly.dev/" style="color: #007bff; text-decoration: none; font-weight: bold;">トレンド</a>サマリーをお届けします。</p>
            """
            
            # カテゴリ名のマッピング
            category_names = {
                'google_trends': 'Google Trends',
                'youtube_trends': 'YouTube',
                'music_trends': 'Spotify',
                'worldnews_trends': 'World News',
                'news_trends': 'World News',  # news_trends_jpはWorld News APIの日本版データを使用
                'podcast_trends': 'Podcast',
                'rakuten_trends': '楽天',
                'hatena_trends': 'はてなブックマーク',
                'twitch_trends': 'Twitch',
                'reddit_trends': 'Reddit',
                'hackernews_trends': 'Hacker News',
                'cnn_trends': 'CNN News',
                'producthunt_trends': 'Product Hunt',
                'nhk_trends': 'NHK ニュース',
                'qiita_trends': 'Qiita トレンド',
                'stock_trends': '株価トレンド',
                'crypto_trends': '仮想通貨トレンド',
                'github_trends': 'GitHub',
                'appstore_trends': 'App Store',
                'movie_trends': '映画トレンド',
                'book_trends': '本トレンド',
                'cisa_kev_trends': 'CISA KEV',
                'thehackernews_trends': 'The Hacker News',
                'devto_trends': 'DEV.to',
                'medium_trends': 'Medium',
                'ebay_trends': 'eBay Popular/Trending'
            }
            
            # フロントエンドのカテゴリ形式をtrends_dataのキー形式に変換
            def normalize_category(cat):
                """カテゴリ名を正規化（google_trends_jp -> google_trends）"""
                if cat.endswith('_jp') or cat.endswith('_us'):
                    return cat.rsplit('_', 1)[0]
                return cat
            
            # 各カテゴリのデータを表示
            has_data = False
            for category in categories:
                normalized_category = normalize_category(category)
                # trends_dataのキーは元のカテゴリ名（_jpや_us付き）なので、元のカテゴリ名で探す
                if category in trends_data and trends_data[category].get('data'):
                    data_list = trends_data[category]['data']
                    if data_list and len(data_list) > 0:
                        has_data = True
                        category_name = category_names.get(normalized_category, normalized_category)
                        html += f"""
                        <div class="category">
                            <div class="category-title">{category_name}</div>
                            <div class="category-content">
                        """
                        
                        for i, item in enumerate(data_list[:5], 1):
                            if normalized_category == 'google_trends':
                                title = item.get('keyword', 'N/A')
                                score = item.get('score', 0)
                                html += f'<div class="trend-item">{i}. {title} (スコア: {score})</div>'
                            elif normalized_category == 'youtube_trends':
                                title = item.get('title', 'N/A')
                                channel = item.get('channel_title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title} - {channel}</div>'
                            elif normalized_category == 'music_trends':
                                title = item.get('title', 'N/A')
                                artist = item.get('artist', 'N/A')
                                html += f'<div class="trend-item">{i}. {title} - {artist}</div>'
                            elif normalized_category == 'worldnews_trends' or normalized_category == 'news_trends':
                                title = item.get('title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'podcast_trends':
                                title = item.get('title', 'N/A')
                                publisher = item.get('publisher', '')
                                # publisherが'Unknown'や空の場合は表示しない
                                if publisher and publisher != 'Unknown':
                                    html += f'<div class="trend-item">{i}. {title} - {publisher}</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'rakuten_trends':
                                title = item.get('title', 'N/A')
                                price = item.get('price', 0)
                                # 価格が文字列の場合は整数に変換
                                try:
                                    if isinstance(price, str):
                                        price = int(float(price.replace(',', '').replace('¥', '').replace('円', '').strip()))
                                    elif not isinstance(price, (int, float)):
                                        price = 0
                                    price_str = f'¥{price:,}' if price and price > 0 else '価格不明'
                                except (ValueError, TypeError):
                                    price_str = '価格不明'
                                html += f'<div class="trend-item">{i}. {title} - {price_str}</div>'
                            elif normalized_category == 'hatena_trends':
                                title = item.get('title', 'N/A')
                                bookmark_count = item.get('bookmark_count', 0)
                                html += f'<div class="trend-item">{i}. {title} ({bookmark_count}ブックマーク)</div>'
                            elif normalized_category == 'twitch_trends':
                                # Twitchはゲームの場合name、ストリームの場合titleを使用
                                name = item.get('name') or item.get('title') or item.get('game_name') or 'N/A'
                                viewer_count = item.get('viewer_count', 0)
                                html += f'<div class="trend-item">{i}. {name} ({viewer_count:,}視聴者)</div>'
                            elif normalized_category == 'reddit_trends':
                                title = item.get('title', 'N/A')
                                subreddit = item.get('subreddit', 'N/A')
                                html += f'<div class="trend-item">{i}. {title} - r/{subreddit}</div>'
                            elif normalized_category == 'hackernews_trends':
                                title = item.get('title', 'N/A')
                                score = item.get('score', 0)
                                html += f'<div class="trend-item">{i}. {title} ({score}ポイント)</div>'
                            elif normalized_category == 'cnn_trends':
                                title = item.get('title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'producthunt_trends':
                                title = item.get('name', 'N/A') or item.get('title', 'N/A')
                                tagline = item.get('tagline', '')
                                votes = item.get('votes', 0)
                                if tagline:
                                    html += f'<div class="trend-item">{i}. {title} - {tagline} ({votes}票)</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title} ({votes}票)</div>'
                            elif normalized_category == 'nhk_trends':
                                title = item.get('title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'qiita_trends':
                                title = item.get('title', 'N/A')
                                likes_count = item.get('likes_count', 0)
                                html += f'<div class="trend-item">{i}. {title} ({likes_count}いいね)</div>'
                            elif normalized_category == 'stock_trends':
                                name = item.get('name', 'N/A')
                                symbol = item.get('symbol', 'N/A')
                                change_percent = item.get('change_percent', 0)
                                change_symbol = '↑' if change_percent >= 0 else '↓'
                                html += f'<div class="trend-item">{i}. {name} ({symbol}) {change_symbol} {abs(change_percent):.2f}%</div>'
                            elif normalized_category == 'crypto_trends':
                                name = item.get('name', 'N/A')
                                symbol = item.get('symbol', 'N/A')
                                price_change = item.get('price_change_percentage_24h', 0)
                                change_symbol = '↑' if price_change >= 0 else '↓'
                                html += f'<div class="trend-item">{i}. {name} ({symbol}) {change_symbol} {abs(price_change):.2f}%</div>'
                            elif normalized_category == 'cisa_kev_trends':
                                title = item.get('title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'thehackernews_trends':
                                title = item.get('title', 'N/A')
                                html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'devto_trends':
                                title = item.get('title', 'N/A')
                                author = item.get('author', '')
                                reactions = item.get('positive_reactions_count', 0)
                                if author:
                                    html += f'<div class="trend-item">{i}. {title} by {author} ({reactions} reactions)</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title} ({reactions} reactions)</div>'
                            elif normalized_category == 'medium_trends':
                                title = item.get('title', 'N/A')
                                author = item.get('author', '')
                                if author:
                                    html += f'<div class="trend-item">{i}. {title} by {author}</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'ebay_trends':
                                title = item.get('title', 'N/A')
                                price = item.get('price', '')
                                currency = item.get('currency', 'USD')
                                if price:
                                    html += f'<div class="trend-item">{i}. {title} - {currency} {price}</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'github_trends':
                                name = item.get('name', 'N/A') or item.get('repo', 'N/A')
                                stars = item.get('stars', 0) or item.get('stargazers_count', 0)
                                html += f'<div class="trend-item">{i}. {name} ({stars}⭐)</div>'
                            elif normalized_category == 'appstore_trends':
                                name = item.get('name', 'N/A') or item.get('title', 'N/A')
                                rating = item.get('rating', 0)
                                if rating:
                                    html += f'<div class="trend-item">{i}. {name} ({rating}★)</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {name}</div>'
                            elif normalized_category == 'movie_trends':
                                title = item.get('title', 'N/A') or item.get('name', 'N/A')
                                rating = item.get('rating', 0) or item.get('vote_average', 0)
                                if rating:
                                    html += f'<div class="trend-item">{i}. {title} ({rating}★)</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title}</div>'
                            elif normalized_category == 'book_trends':
                                title = item.get('title', 'N/A') or item.get('name', 'N/A')
                                author = item.get('author', '')
                                if author:
                                    html += f'<div class="trend-item">{i}. {title} by {author}</div>'
                                else:
                                    html += f'<div class="trend-item">{i}. {title}</div>'
                    
                        html += """
                            </div>
                        </div>
                        """
            
            # データが1件もない場合のメッセージ
            if not has_data:
                html += """
                    <div class="category">
                        <div class="category-content">
                            <p>現在、トレンドデータが取得できませんでした。しばらくしてから再度お試しください。</p>
                            <p><a href="https://trends-dashboard.fly.dev/">ダッシュボード</a>で最新のトレンド情報を確認できます。</p>
                        </div>
                    </div>
                """
            
            html += f"""
                </div>
                
                <div class="footer">
                    <p>このメールは自動配信されています。</p>
                    <p>配信を停止したい場合は、以下のリンクをクリックしてください：</p>
                    <p><a href="{unsubscribe_url}" style="color: #dc3545; text-decoration: none; font-weight: bold; padding: 10px 20px; background-color: #f8f9fa; border: 1px solid #dc3545; border-radius: 5px; display: inline-block;">配信を停止する</a></p>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"❌ HTML作成エラー: {e}", exc_info=True)
            return "<html><body><p>トレンドサマリー配信</p></body></html>"
    
    def _create_trends_summary_text(self, trends_data, categories, unsubscribe_token=None):
        """トレンドサマリー配信メールのテキスト内容を作成
        
        Args:
            trends_data: トレンドデータの辞書
            categories: カテゴリのリスト
            unsubscribe_token: 登録解除トークン（オプション）
        """
        try:
            # カテゴリをサブスクリプションページの順序でソート
            categories = self._sort_categories_by_order(categories)
            
            # 配信停止URLを生成
            if unsubscribe_token:
                unsubscribe_url = f"https://trends-dashboard.fly.dev/subscription/unsubscribe/{unsubscribe_token}"
            else:
                unsubscribe_url = "https://trends-dashboard.fly.dev/subscription/"
            
            text = f"📊 トレンドサマリー配信 - {datetime.now().strftime('%Y年%m月%d日')}\n\n"
            text += "こんにちは！本日のトレンドサマリーをお届けします。\n"
            text += "ダッシュボード: https://trends-dashboard.fly.dev/\n\n"
            
            # カテゴリ名のマッピング
            category_names = {
                'google_trends': 'Google Trends',
                'youtube_trends': 'YouTube',
                'music_trends': 'Spotify',
                'worldnews_trends': 'World News',
                'news_trends': 'World News',  # news_trends_jpはWorld News APIの日本版データを使用
                'podcast_trends': 'Podcast',
                'rakuten_trends': '楽天',
                'hatena_trends': 'はてなブックマーク',
                'twitch_trends': 'Twitch',
                'reddit_trends': 'Reddit',
                'hackernews_trends': 'Hacker News',
                'cnn_trends': 'CNN News',
                'producthunt_trends': 'Product Hunt',
                'nhk_trends': 'NHK ニュース',
                'qiita_trends': 'Qiita トレンド',
                'stock_trends': '株価トレンド',
                'crypto_trends': '仮想通貨トレンド',
                'github_trends': 'GitHub',
                'appstore_trends': 'App Store',
                'movie_trends': '映画トレンド',
                'book_trends': '本トレンド',
                'cisa_kev_trends': 'CISA KEV',
                'thehackernews_trends': 'The Hacker News',
                'devto_trends': 'DEV.to',
                'medium_trends': 'Medium',
                'ebay_trends': 'eBay Popular/Trending'
            }
            
            # フロントエンドのカテゴリ形式をtrends_dataのキー形式に変換
            def normalize_category(cat):
                """カテゴリ名を正規化（google_trends_jp -> google_trends）"""
                if cat.endswith('_jp') or cat.endswith('_us'):
                    return cat.rsplit('_', 1)[0]
                return cat
            
            # 各カテゴリのデータを表示
            has_data = False
            for category in categories:
                normalized_category = normalize_category(category)
                # trends_dataのキーは元のカテゴリ名（_jpや_us付き）なので、元のカテゴリ名で探す
                if category in trends_data and trends_data[category].get('data'):
                    data_list = trends_data[category]['data']
                    if data_list and len(data_list) > 0:
                        has_data = True
                        category_name = category_names.get(normalized_category, normalized_category)
                        text += f"【{category_name}】\n"
                        
                        for i, item in enumerate(data_list[:5], 1):
                            if normalized_category == 'google_trends':
                                title = item.get('keyword', 'N/A')
                                score = item.get('score', 0)
                                text += f"{i}. {title} (スコア: {score})\n"
                            elif normalized_category == 'youtube_trends':
                                title = item.get('title', 'N/A')
                                channel = item.get('channel_title', 'N/A')
                                text += f"{i}. {title} - {channel}\n"
                            elif normalized_category == 'music_trends':
                                title = item.get('title', 'N/A')
                                artist = item.get('artist', 'N/A')
                                text += f"{i}. {title} - {artist}\n"
                            elif normalized_category == 'worldnews_trends' or normalized_category == 'news_trends':
                                title = item.get('title', 'N/A')
                                text += f"{i}. {title}\n"
                            elif normalized_category == 'podcast_trends':
                                title = item.get('title', 'N/A')
                                publisher = item.get('publisher', '')
                                # publisherが'Unknown'や空の場合は表示しない
                                if publisher and publisher != 'Unknown':
                                    text += f"{i}. {title} - {publisher}\n"
                                else:
                                    text += f"{i}. {title}\n"
                            elif normalized_category == 'rakuten_trends':
                                title = item.get('title', 'N/A')
                                price = item.get('price', 0)
                                # 価格が文字列の場合は整数に変換
                                try:
                                    if isinstance(price, str):
                                        price = int(float(price.replace(',', '').replace('¥', '').replace('円', '').strip()))
                                    elif not isinstance(price, (int, float)):
                                        price = 0
                                    price_str = f'¥{price:,}' if price and price > 0 else '価格不明'
                                except (ValueError, TypeError):
                                    price_str = '価格不明'
                                text += f"{i}. {title} - {price_str}\n"
                            elif normalized_category == 'hatena_trends':
                                title = item.get('title', 'N/A')
                                bookmark_count = item.get('bookmark_count', 0)
                                text += f"{i}. {title} ({bookmark_count}ブックマーク)\n"
                            elif normalized_category == 'twitch_trends':
                                # Twitchはゲームの場合name、ストリームの場合titleを使用
                                name = item.get('name') or item.get('title') or item.get('game_name') or 'N/A'
                                viewer_count = item.get('viewer_count', 0)
                                text += f"{i}. {name} ({viewer_count:,}視聴者)\n"
                            elif normalized_category == 'reddit_trends':
                                title = item.get('title', 'N/A')
                                subreddit = item.get('subreddit', 'N/A')
                                text += f"{i}. {title} - r/{subreddit}\n"
                            elif normalized_category == 'hackernews_trends':
                                title = item.get('title', 'N/A')
                                score = item.get('score', 0)
                                text += f"{i}. {title} ({score}ポイント)\n"
                            elif normalized_category == 'cnn_trends':
                                title = item.get('title', 'N/A')
                                text += f"{i}. {title}\n"
                            elif normalized_category == 'producthunt_trends':
                                title = item.get('name', 'N/A') or item.get('title', 'N/A')
                                tagline = item.get('tagline', '')
                                votes = item.get('votes', 0)
                                if tagline:
                                    text += f"{i}. {title} - {tagline} ({votes}票)\n"
                                else:
                                    text += f"{i}. {title} ({votes}票)\n"
                            elif normalized_category == 'nhk_trends':
                                title = item.get('title', 'N/A')
                                text += f"{i}. {title}\n"
                            elif normalized_category == 'qiita_trends':
                                title = item.get('title', 'N/A')
                                likes_count = item.get('likes_count', 0)
                                text += f"{i}. {title} ({likes_count}いいね)\n"
                            elif normalized_category == 'stock_trends':
                                name = item.get('name', 'N/A')
                                symbol = item.get('symbol', 'N/A')
                                change_percent = item.get('change_percent', 0)
                                change_symbol = '↑' if change_percent >= 0 else '↓'
                                text += f"{i}. {name} ({symbol}) {change_symbol} {abs(change_percent):.2f}%\n"
                            elif normalized_category == 'crypto_trends':
                                name = item.get('name', 'N/A')
                                symbol = item.get('symbol', 'N/A')
                                price_change = item.get('price_change_percentage_24h', 0)
                                change_symbol = '↑' if price_change >= 0 else '↓'
                                text += f"{i}. {name} ({symbol}) {change_symbol} {abs(price_change):.2f}%\n"
                            elif normalized_category == 'cisa_kev_trends':
                                title = item.get('title', 'N/A')
                                text += f"{i}. {title}\n"
                            elif normalized_category == 'thehackernews_trends':
                                title = item.get('title', 'N/A')
                                text += f"{i}. {title}\n"
                            elif normalized_category == 'devto_trends':
                                title = item.get('title', 'N/A')
                                author = item.get('author', '')
                                reactions = item.get('positive_reactions_count', 0)
                                if author:
                                    text += f"{i}. {title} by {author} ({reactions} reactions)\n"
                                else:
                                    text += f"{i}. {title} ({reactions} reactions)\n"
                            elif normalized_category == 'medium_trends':
                                title = item.get('title', 'N/A')
                                author = item.get('author', '')
                                if author:
                                    text += f"{i}. {title} by {author}\n"
                                else:
                                    text += f"{i}. {title}\n"
                            elif normalized_category == 'ebay_trends':
                                title = item.get('title', 'N/A')
                                price = item.get('price', '')
                                currency = item.get('currency', 'USD')
                                if price:
                                    text += f"{i}. {title} - {currency} {price}\n"
                                else:
                                    text += f"{i}. {title}\n"
                            elif normalized_category == 'github_trends':
                                name = item.get('name', 'N/A') or item.get('repo', 'N/A')
                                stars = item.get('stars', 0) or item.get('stargazers_count', 0)
                                text += f"{i}. {name} ({stars}⭐)\n"
                            elif normalized_category == 'appstore_trends':
                                name = item.get('name', 'N/A') or item.get('title', 'N/A')
                                rating = item.get('rating', 0)
                                if rating:
                                    text += f"{i}. {name} ({rating}★)\n"
                                else:
                                    text += f"{i}. {name}\n"
                            elif normalized_category == 'movie_trends':
                                title = item.get('title', 'N/A') or item.get('name', 'N/A')
                                rating = item.get('rating', 0) or item.get('vote_average', 0)
                                if rating:
                                    text += f"{i}. {title} ({rating}★)\n"
                                else:
                                    text += f"{i}. {title}\n"
                            elif normalized_category == 'book_trends':
                                title = item.get('title', 'N/A') or item.get('name', 'N/A')
                                author = item.get('author', '')
                                if author:
                                    text += f"{i}. {title} by {author}\n"
                                else:
                                    text += f"{i}. {title}\n"
                    
                        text += "\n"
            
            # データが1件もない場合のメッセージ
            if not has_data:
                text += "現在、トレンドデータが取得できませんでした。しばらくしてから再度お試しください。\n"
                text += "ダッシュボード: https://trends-dashboard.fly.dev/\n\n"
            
            text += "\nこのメールは自動配信されています。\n"
            text += f"配信を停止したい場合は、以下のURLにアクセスしてください：\n{unsubscribe_url}\n"
            
            return text
            
        except Exception as e:
            logger.error(f"❌ テキスト作成エラー: {e}", exc_info=True)
            return "トレンドサマリー配信"

    def _create_confirmation_html(self, email: str, frequency: str, categories: List[str], unsubscribe_token: str) -> str:
        """確認メールのHTML内容を作成"""
        frequency_text = {
            'daily': '毎日',
            'weekly': '毎週',
            'monthly': '毎月'
        }.get(frequency, frequency)
        
        # カテゴリ名のマッピング（フロントエンドの値に対応）
        category_names = {
            # 日本のカテゴリ
            'google_trends_jp': 'Google Trends (日本)',
            'youtube_trends_jp': 'YouTube トレンド (日本)',
            'music_trends_jp': '音楽トレンド (日本)',
            'news_trends_jp': 'ニューストレンド (日本)',
            'podcast_trends_jp': 'ポッドキャストトレンド (日本)',
            'rakuten_trends_jp': '楽天商品トレンド (日本)',
            'hatena_trends_jp': 'はてなブックマークトレンド (日本)',
            'twitch_trends_jp': 'Twitchゲームトレンド (日本)',
            'movie_trends_jp': '映画トレンド (日本)',
            'book_trends_jp': '本トレンド (日本)',
            'github_trends_jp': 'GitHubトレンド (日本)',
            'appstore_trends_jp': 'App Storeトレンド (日本)',
            # USのカテゴリ
            'google_trends_us': 'Google Trends (US)',
            'youtube_trends_us': 'YouTube トレンド (US)',
            'music_trends_us': '音楽トレンド (US)',
            'worldnews_trends_us': 'World News (US)',
            'podcast_trends_us': 'ポッドキャストトレンド (US)',
            'twitch_trends_us': 'Twitchゲームトレンド (US)',
            'reddit_trends_us': 'Reddit (US)',
            'hackernews_trends_us': 'Hacker News (US)',
            'producthunt_trends_us': 'Product Hunt (US)',
            'devto_trends_us': 'DEV.to (US)',
            'medium_trends_us': 'Medium (US)',
            'cisa_kev_trends_us': 'CISA KEV (US)',
            'thehackernews_trends_us': 'The Hacker News (US)',
            'cnn_trends_us': 'CNN News (US)',
            'github_trends_us': 'GitHub (US)',
            'appstore_trends_us': 'App Store (US)',
            'stock_trends_us': 'Stock Trends (US)',
            'crypto_trends_us': 'Cryptocurrency Trends (US)',
            'movie_trends_us': '映画トレンド (US)',
            'book_trends_us': '本トレンド (US)',
            'ebay_trends_us': 'eBay Popular/Trending (US)',
            # 日本のカテゴリ（追加）
            'nhk_trends_jp': 'NHK ニュース (日本)',
            'qiita_trends_jp': 'Qiita トレンド (日本)',
            'stock_trends_jp': '株価トレンド (日本)',
            'crypto_trends_jp': '仮想通貨トレンド',
            # 旧形式との互換性（念のため）
            'google_trends': 'Google Trends',
            'youtube_trends': 'YouTube',
            'music_trends': '音楽',
            'worldnews_trends': 'ニュース',
            'podcast_trends': 'ポッドキャスト',
            'rakuten_trends': '楽天',
            'hatena_trends': 'はてなブックマーク',
            'twitch_trends': 'Twitch'
        }
        
        # 選択されたカテゴリ名のリストを作成
        if not categories or len(categories) == 0:
            # カテゴリが選択されていない場合は全カテゴリを表示
            selected_categories = list(category_names.values())
        else:
            selected_categories = [category_names.get(cat, cat) for cat in categories if cat in category_names]
        
        # カテゴリが空の場合は「全カテゴリ」を表示
        if len(selected_categories) == 0:
            categories_text = '全カテゴリの最新トレンド情報'
        else:
            categories_text = '、'.join(selected_categories) + 'の最新トレンド情報'
        
        unsubscribe_url = f"http://localhost:5000/subscription/unsubscribe/{unsubscribe_token}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>サブスクリプション登録確認</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ color: #007bff; margin: 0; }}
                .content {{ line-height: 1.6; color: #333; }}
                .highlight {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
                .unsubscribe {{ margin-top: 15px; }}
                .unsubscribe a {{ color: #dc3545; text-decoration: none; }}
                .btn {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📧 サブスクリプション登録確認</h1>
                </div>
                <div class="content">
                    <p>この度は、トレンドサマリー配信サービスにご登録いただき、ありがとうございます！</p>
                    
                    <div class="highlight">
                        <h3>📊 登録情報</h3>
                        <p><strong>メールアドレス:</strong> {email}</p>
                        <p><strong>配信頻度:</strong> {frequency_text}</p>
                        <p><strong>配信内容:</strong> {categories_text}</p>
                    </div>
                    
                    <p>毎朝5時に更新される最新のトレンド情報を、指定された頻度でお届けいたします。</p>
                    
                    <p>配信を停止したい場合は、以下のリンクをクリックしてください：</p>
                    <a href="{unsubscribe_url}" class="btn">配信を停止する</a>
                </div>
                <div class="footer">
                    <p>このメールは自動送信されています。</p>
                    <div class="unsubscribe">
                        <p>配信を停止する: <a href="{unsubscribe_url}">こちらをクリック</a></p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def _create_confirmation_text(self, email: str, frequency: str, categories: List[str], unsubscribe_token: str) -> str:
        """確認メールのテキスト内容を作成"""
        frequency_text = {
            'daily': '毎日',
            'weekly': '毎週',
            'monthly': '毎月'
        }.get(frequency, frequency)
        
        # カテゴリ名のマッピング（フロントエンドの値に対応）
        category_names = {
            # 日本のカテゴリ
            'google_trends_jp': 'Google Trends (日本)',
            'youtube_trends_jp': 'YouTube トレンド (日本)',
            'music_trends_jp': '音楽トレンド (日本)',
            'news_trends_jp': 'ニューストレンド (日本)',
            'podcast_trends_jp': 'ポッドキャストトレンド (日本)',
            'rakuten_trends_jp': '楽天商品トレンド (日本)',
            'hatena_trends_jp': 'はてなブックマークトレンド (日本)',
            'twitch_trends_jp': 'Twitchゲームトレンド (日本)',
            # USのカテゴリ
            'google_trends_us': 'Google Trends (US)',
            'youtube_trends_us': 'YouTube トレンド (US)',
            'music_trends_us': '音楽トレンド (US)',
            'worldnews_trends_us': 'World News (US)',
            'podcast_trends_us': 'ポッドキャストトレンド (US)',
            'twitch_trends_us': 'Twitchゲームトレンド (US)',
            'reddit_trends_us': 'Reddit (US)',
            'hackernews_trends_us': 'Hacker News (US)',
            'producthunt_trends_us': 'Product Hunt (US)',
            'devto_trends_us': 'DEV.to (US)',
            'medium_trends_us': 'Medium (US)',
            'cisa_kev_trends_us': 'CISA KEV (US)',
            'thehackernews_trends_us': 'The Hacker News (US)',
            'cnn_trends_us': 'CNN News (US)',
            'github_trends_us': 'GitHub (US)',
            'appstore_trends_us': 'App Store (US)',
            'stock_trends_us': 'Stock Trends (US)',
            'crypto_trends_us': 'Cryptocurrency Trends (US)',
            'movie_trends_us': 'Movie Trends (US)',
            'book_trends_us': 'Book Trends (US)',
            'ebay_trends_us': 'eBay Popular/Trending (US)',
            # 日本のカテゴリ（追加）
            'nhk_trends_jp': 'NHK ニュース (日本)',
            'qiita_trends_jp': 'Qiita トレンド (日本)',
            'stock_trends_jp': '株価トレンド (日本)',
            'crypto_trends_jp': '仮想通貨トレンド',
            # 旧形式との互換性（念のため）
            'google_trends': 'Google Trends',
            'youtube_trends': 'YouTube',
            'music_trends': '音楽',
            'worldnews_trends': 'ニュース',
            'podcast_trends': 'ポッドキャスト',
            'rakuten_trends': '楽天',
            'hatena_trends': 'はてなブックマーク',
            'twitch_trends': 'Twitch'
        }
        
        # 選択されたカテゴリ名のリストを作成
        if not categories or len(categories) == 0:
            # カテゴリが選択されていない場合は全カテゴリを表示
            selected_categories = list(category_names.values())
        else:
            selected_categories = [category_names.get(cat, cat) for cat in categories if cat in category_names]
        
        # カテゴリが空の場合は「全カテゴリ」を表示
        if len(selected_categories) == 0:
            categories_text = '全カテゴリの最新トレンド情報'
        else:
            categories_text = '、'.join(selected_categories) + 'の最新トレンド情報'
        
        unsubscribe_url = f"http://localhost:5000/subscription/unsubscribe/{unsubscribe_token}"
        
        text = f"""
📧 サブスクリプション登録確認

この度は、トレンドサマリー配信サービスにご登録いただき、ありがとうございます！

📊 登録情報
メールアドレス: {email}
配信頻度: {frequency_text}
配信内容: {categories_text}

毎朝5時に更新される最新のトレンド情報を、指定された頻度でお届けいたします。

配信を停止したい場合は、以下のURLにアクセスしてください：
{unsubscribe_url}

このメールは自動送信されています。
        """
        return text


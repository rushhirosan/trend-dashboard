import os
import requests
import json
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from database_config import TrendsCache

class HatenaTrendsManager:
    """はてなブックマークトレンド管理クラス（公式RSS + API使用）"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://b.hatena.ne.jp"
        self.count_api_url = "https://bookmark.hatenaapis.com/count/entry"
        self.entry_api_url = "https://b.hatena.ne.jp/entry/json"
        self.db = TrendsCache()
        
        print(f"はてなブックマーク Trends Manager初期化:")
        print(f"  ホットエントリーRSS: {self.base_url}/hotentry.rss")
        print(f"  Count API: {self.count_api_url}")
        print(f"  Entry API: {self.entry_api_url}")
    
    def get_trends(self, category='all', limit=25, force_refresh=False):
        """はてなブックマークトレンドを取得（get_hot_entriesのエイリアス）"""
        return self.get_hot_entries(category, limit, force_refresh)
    
    def get_hot_entries(self, category='all', limit=25, force_refresh=False):
        """はてなブックマークのホットエントリーを取得（公式RSS使用）"""
        try:
            # キャッシュから取得を試行
            cache_key = 'hatena_trends'
            cached_data = self.get_from_cache(cache_key)
            if cached_data and not force_refresh:
                cache_info = self._get_cache_info(cache_key)
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'category': category,
                    'cache_info': cache_info
                }
            
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache('hatena_trends'):
                print(f"⚠️ はてなブックマークのキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                if cached_data:
                    cache_info = self._get_cache_info(cache_key)
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'category': category,
                        'cache_info': cache_info
                    }
                else:
                    # キャッシュデータがない場合は空のデータを返す
                    return {
                        'data': [],
                        'status': 'no_cache',
                        'category': category,
                        'cache_info': {'last_updated': None, 'data_count': 0}
                    }
            # カテゴリー別RSS URLを構築
            if category == 'all':
                rss_url = f"{self.base_url}/hotentry.rss"
            else:
                rss_url = f"{self.base_url}/hotentry/{category}.rss"
            
            print(f"はてなブックマークホットエントリーRSS取得開始: {rss_url}")
            
            # RSSフィードを取得
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                return {'error': 'RSSフィードからエントリーを取得できませんでした'}
            
            # エントリー情報を抽出
            items = []
            for entry in feed.entries[:limit]:
                # 公開日時を適切にフォーマット
                published = entry.get('published', '') or entry.get('updated', '') or entry.get('created', '')
                if published:
                    try:
                        from datetime import datetime
                        import email.utils
                        # RFC 2822形式の日付をパース
                        parsed_date = email.utils.parsedate_tz(published)
                        if parsed_date:
                            dt = datetime(*parsed_date[:6])
                            published = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        # パースに失敗した場合は元の文字列を使用
                        published = published
                else:
                    # 日付が取得できない場合は現在時刻を使用
                    from datetime import datetime
                    published = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                item = {
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'description': entry.get('summary', ''),
                    'published': published,
                    'author': entry.get('author', ''),
                    'category': category
                }
                
                # ブックマーク数を取得
                item['bookmark_count'] = self._get_bookmark_count(item['url'])
                items.append(item)
            
            # ランクを付与（RSSの順序を保持）
            trends_data = []
            for i, item in enumerate(items):
                trends_data.append({
                    'rank': i + 1,
                    'title': item['title'],
                    'url': item['url'],
                    'description': item['description'],
                    'bookmark_count': item['bookmark_count'],
                    'published': item['published'],
                    'author': item['author'],
                    'category': item['category']
                })
            
            # キャッシュに保存
            self.save_to_cache(trends_data, cache_key)
            # 更新日時を記録
            self._update_refresh_time(cache_key)
            
            return {
                'data': trends_data,
                'status': 'success',
                'source': f'はてなブックマークホットエントリー（{category}）',
                'total_count': len(trends_data),
                'category': category
            }
                
        except Exception as e:
            return {'error': f'はてなブックマークトレンド取得エラー: {str(e)}'}
    
    def get_new_entries(self, category='all', limit=25):
        """はてなブックマークの新着エントリーを取得（公式RSS使用）"""
        try:
            # カテゴリー別新着RSS URLを構築
            if category == 'all':
                rss_url = f"{self.base_url}/entrylist.rss"
            else:
                rss_url = f"{self.base_url}/entrylist/{category}.rss"
            
            print(f"はてなブックマーク新着エントリーRSS取得開始: {rss_url}")
            
            # RSSフィードを取得
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                return {'error': 'RSSフィードからエントリーを取得できませんでした'}
            
            # エントリー情報を抽出
            items = []
            for entry in feed.entries[:limit]:
                # 公開日時を適切にフォーマット
                published = entry.get('published', '') or entry.get('updated', '') or entry.get('created', '')
                if published:
                    try:
                        from datetime import datetime
                        import email.utils
                        # RFC 2822形式の日付をパース
                        parsed_date = email.utils.parsedate_tz(published)
                        if parsed_date:
                            dt = datetime(*parsed_date[:6])
                            published = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        # パースに失敗した場合は元の文字列を使用
                        published = published
                else:
                    # 日付が取得できない場合は現在時刻を使用
                    from datetime import datetime
                    published = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                item = {
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'description': entry.get('summary', ''),
                    'published': published,
                    'author': entry.get('author', ''),
                    'category': category
                }
                
                # ブックマーク数を取得
                item['bookmark_count'] = self._get_bookmark_count(item['url'])
                items.append(item)
            
            # ランクを付与（RSSの順序を保持）
            trends_data = []
            for i, item in enumerate(items):
                trends_data.append({
                    'rank': i + 1,
                    'title': item['title'],
                    'url': item['url'],
                    'description': item['description'],
                    'bookmark_count': item['bookmark_count'],
                    'published': item['published'],
                    'author': item['author'],
                    'category': item['category']
                })
            
            return {
                'data': trends_data,
                'status': 'success',
                'source': f'はてなブックマーク新着エントリー（{category}）',
                'total_count': len(trends_data),
                'category': category
            }
                
        except Exception as e:
            return {'error': f'はてなブックマーク新着エントリー取得エラー: {str(e)}'}
    
    def _get_bookmark_count(self, url):
        """はてなブックマークCount APIでブックマーク数を取得"""
        try:
            params = {'url': url}
            response = requests.get(self.count_api_url, params=params, timeout=5)
            
            if response.status_code == 200:
                # 返り値は数値 or "null"（存在しない場合）
                try:
                    count_text = response.text.strip()
                    if count_text.isdigit():
                        return int(count_text)
                    else:
                        return 0
                except:
                    return 0
            else:
                return 0
                
        except Exception as e:
            print(f"ブックマーク数取得エラー: {e}")
            return 0
    
    def get_entry_details(self, url):
        """はてなブックマークEntry APIでエントリー詳細を取得"""
        try:
            params = {'url': url}
            response = requests.get(self.entry_api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'title': data.get('title', ''),
                    'url': data.get('url', ''),
                    'bookmarks': data.get('bookmarks', []),
                    'tags': data.get('tags', []),
                    'screenshot': data.get('screenshot', ''),
                    'eid': data.get('eid', '')
                }
            else:
                return None
                
        except Exception as e:
            print(f"エントリー詳細取得エラー: {e}")
            return None
    
    def get_available_categories(self):
        """利用可能なカテゴリー一覧を取得"""
        return [
            'all',      # 総合
            'it',       # テクノロジー
            'social',   # 社会
            'economics', # 経済
            'life',     # 生活
            'knowledge', # 知識
            'entertainment', # エンタメ
            'game',     # ゲーム
            'fun',      # おもしろ
            'movie',    # 映画
            'gourmet',  # グルメ
            'love',     # 恋愛
            'hotel',    # ホテル
            'sports',   # スポーツ
            'anime',    # アニメ
            'comic',    # コミック
            'design',   # デザイン
            'science',  # 科学
            'gadgets',  # ガジェット
            'car',      # 自動車
            'career',   # キャリア
            'kaden',    # 家電
            'all4',     # 4コマ
            'watch',    # 時計
            'manga',    # マンガ
            'book',     # 本
            'camera',   # カメラ
            'music',    # 音楽
            'tv',       # テレビ
            'travel',   # 旅行
            'fashion',  # ファッション
            'beauty',   # 美容
            'health',   # 健康
            'cooking',  # 料理
            'pet',      # ペット
            'hobby',    # 趣味
            'art',      # アート
            'photo',    # 写真
            'movie-eng', # 映画（英語）
            'news',     # ニュース
            'security', # セキュリティ
            'mobile',   # モバイル
            'web',      # Web
            'programming', # プログラミング
            'database', # データベース
            'server',   # サーバー
            'linux',    # Linux
            'windows',  # Windows
            'mac',      # Mac
            'iphone',   # iPhone
            'android',  # Android
            'google',   # Google
            'amazon',   # Amazon
            'microsoft', # Microsoft
            'apple',    # Apple
            'facebook', # Facebook
            'twitter',  # Twitter
            'youtube',  # YouTube
            'instagram', # Instagram
            'tiktok',   # TikTok
            'netflix',  # Netflix
            'spotify',  # Spotify
            'uber',     # Uber
            'airbnb',   # Airbnb
            'tesla',    # Tesla
            'spacex',   # SpaceX
            'nasa',     # NASA
            'covid19',  # COVID-19
            'vaccine',  # ワクチン
            'climate',  # 気候変動
            'ai',       # AI
            'ml',       # 機械学習
            'blockchain', # ブロックチェーン
            'crypto',   # 暗号通貨
            'nft',      # NFT
            'metaverse', # メタバース
            'web3',     # Web3
            'vr',       # VR
            'ar',       # AR
            'iot',      # IoT
            '5g',       # 5G
            'quantum',  # 量子コンピュータ
            'robot',    # ロボット
            'drone',    # ドローン
            'ev',       # 電気自動車
            'hydrogen', # 水素
            'renewable', # 再生可能エネルギー
            'esg',      # ESG
            'sdgs',     # SDGs
            'diversity', # ダイバーシティ
            'inclusion', # インクルージョン
            'equality', # 平等
            'justice',  # 正義
            'democracy', # 民主主義
            'freedom',  # 自由
            'privacy',  # プライバシー
            'security', # セキュリティ
            'cybersecurity', # サイバーセキュリティ
            'hacking',  # ハッキング
            'malware',  # マルウェア
            'phishing', # フィッシング
            'ransomware', # ランサムウェア
            'vpn',      # VPN
            'tor',      # Tor
            'encryption', # 暗号化
            'authentication', # 認証
            'biometric', # 生体認証
            '2fa',      # 二要素認証
            'password', # パスワード
            'backup',   # バックアップ
            'cloud',    # クラウド
            'saas',     # SaaS
            'paas',     # Paas
            'iaas',     # IaaS
            'container', # コンテナ
            'docker',   # Docker
            'kubernetes', # Kubernetes
            'microservices', # マイクロサービス
            'api',      # API
            'rest',     # REST
            'graphql',  # GraphQL
            'json',     # JSON
            'xml',      # XML
            'yaml',     # YAML
            'markdown', # Markdown
            'git',      # Git
            'github',   # GitHub
            'gitlab',   # GitLab
            'bitbucket', # Bitbucket
            'ci',       # CI
            'cd',       # CD
            'devops',   # DevOps
            'agile',    # アジャイル
            'scrum',    # スクラム
            'kanban',   # カンバン
            'lean',     # リーン
            'sixsigma', # シックスシグマ
            'tqm',      # TQM
            'iso',      # ISO
            'pmp',      # PMP
            'prince2',  # PRINCE2
            'itil',     # ITIL
            'cobit',    # COBIT
            'sox',      # SOX
            'gdpr',     # GDPR
            'ccpa',     # CCPA
            'lgpd',     # LGPD
            'pipeda',   # PIPEDA
            'popia',    # POPIA
            'pdpa',     # PDPA
            'appi',     # APPI
            'pipeda',   # PIPEDA
            'lgpd',     # LGPD
            'ccpa',     # CCPA
            'gdpr',     # GDPR
            'sox',      # SOX
            'cobit',    # COBIT
            'itil',     # ITIL
            'prince2',  # PRINCE2
            'pmp',      # PMP
            'iso',      # ISO
            'tqm',      # TQM
            'sixsigma', # シックスシグマ
            'lean',     # リーン
            'kanban',   # カンバン
            'scrum',    # スクラム
            'agile',    # アジャイル
            'devops',   # DevOps
            'cd',       # CD
            'ci',       # CI
            'bitbucket', # Bitbucket
            'gitlab',   # GitLab
            'github',   # GitHub
            'git',      # Git
            'markdown', # Markdown
            'yaml',     # YAML
            'xml',      # XML
            'json',     # JSON
            'graphql',  # GraphQL
            'rest',     # REST
            'api',      # API
            'microservices', # マイクロサービス
            'kubernetes', # Kubernetes
            'docker',   # Docker
            'container', # コンテナ
            'iaas',     # IaaS
            'paas',     # Paas
            'saas',     # SaaS
            'cloud',    # クラウド
            'backup',   # バックアップ
            'password', # パスワード
            '2fa',      # 二要素認証
            'biometric', # 生体認証
            'authentication', # 認証
            'encryption', # 暗号化
            'tor',      # Tor
            'vpn',      # VPN
            'ransomware', # ランサムウェア
            'phishing', # フィッシング
            'malware',  # マルウェア
            'hacking',  # ハッキング
            'cybersecurity', # サイバーセキュリティ
            'security', # セキュリティ
            'privacy',  # プライバシー
            'freedom',  # 自由
            'democracy', # 民主主義
            'justice',  # 正義
            'equality', # 平等
            'inclusion', # インクルージョン
            'diversity', # ダイバーシティ
            'sdgs',     # SDGs
            'esg',      # ESG
            'renewable', # 再生可能エネルギー
            'hydrogen', # 水素
            'ev',       # 電気自動車
            'drone',    # ドローン
            'robot',    # ロボット
            'quantum',  # 量子コンピュータ
            '5g',       # 5G
            'iot',      # IoT
            'ar',       # AR
            'vr',       # VR
            'web3',     # Web3
            'metaverse', # メタバース
            'nft',      # NFT
            'crypto',   # 暗号通貨
            'blockchain', # ブロックチェーン
            'ml',       # 機械学習
            'ai',       # AI
            'climate',  # 気候変動
            'vaccine',  # ワクチン
            'covid19',  # COVID-19
            'spacex',   # SpaceX
            'tesla',    # Tesla
            'airbnb',   # Airbnb
            'uber',     # Uber
            'spotify',  # Spotify
            'netflix',  # Netflix
            'tiktok',   # TikTok
            'instagram', # Instagram
            'twitter',  # Twitter
            'facebook', # Facebook
            'apple',    # Apple
            'microsoft', # Microsoft
            'amazon',   # Amazon
            'google',   # Google
            'android',  # Android
            'iphone',   # iPhone
            'mac',      # Mac
            'windows',  # Windows
            'linux',    # Linux
            'server',   # サーバー
            'database', # データベース
            'programming', # プログラミング
            'web',      # Web
            'mobile',   # モバイル
            'security', # セキュリティ
            'news',     # ニュース
            'movie-eng', # 映画（英語）
            'photo',    # 写真
            'art',      # アート
            'hobby',    # 趣味
            'pet',      # ペット
            'cooking',  # 料理
            'health',   # 健康
            'beauty',   # 美容
            'fashion',  # ファッション
            'travel',   # 旅行
            'tv',       # テレビ
            'music',    # 音楽
            'book',     # 本
            'manga',    # マンガ
            'watch',    # 時計
            'all4',     # 4コマ
            'kaden',    # 家電
            'career',   # キャリア
            'car',      # 自動車
            'gadgets',  # ガジェット
            'science',  # 科学
            'design',   # デザイン
            'comic',    # コミック
            'anime',    # アニメ
            'sports',   # スポーツ
            'hotel',    # ホテル
            'love',     # 恋愛
            'gourmet',  # グルメ
            'movie',    # 映画
            'fun',      # おもしろ
            'game',     # ゲーム
            'entertainment', # エンタメ
            'knowledge', # 知識
            'life',     # 生活
            'economics', # 経済
            'social',   # 社会
            'it'        # テクノロジー
        ]
    
    def get_hatena_trends_summary(self):
        """はてなブックマークトレンドの概要を取得"""
        return {
            'hatena_api': {
                'available': True,
                'note': 'はてなブックマーク公式RSS + API: ホットエントリー、新着エントリー',
                'features': [
                    'ホットエントリー取得（RSS）',
                    '新着エントリー取得（RSS）',
                    'カテゴリー別分類',
                    'ブックマーク数取得（Count API）',
                    'エントリー詳細取得（Entry API）',
                    '公式API使用（スクレイピングなし）'
                ]
            },
            'limitations': [
                'RSS更新頻度に依存',
                'レート制限あり',
                'カテゴリー数が多い'
            ],
            'setup_required': [
                'feedparserライブラリ',
                '公式RSS + API使用'
            ]
        }
    
    def get_from_cache(self, cache_key):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_from_cache('hatena_trends', '')
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, cache_key):
        """データをキャッシュに保存"""
        try:
            self.db.save_hatena_trends_to_cache(data, cache_key)
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def is_cache_valid(self, cache_key):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_hatena_cache_valid(cache_key)
        except Exception as e:
            print(f"キャッシュ有効性チェックエラー: {e}")
            return False
    
    def _should_refresh_cache(self, cache_key):
        """今日既にキャッシュを更新したかチェック（朝5時から夜12時まで）"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            today = now.date()
            current_hour = now.hour
            
            # 時間制限：5時から24時まで
            if not (5 <= current_hour < 24):
                print(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('hatena_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            print(f"キャッシュ更新日時チェックエラー: {e}")
            return True
    
    def _update_refresh_time(self, cache_key):
        """キャッシュ更新日時を記録"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) 
                        DO UPDATE SET 
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('hatena_trends', now, 25))  # 正しいキャッシュキーを使用
                    conn.commit()
        except Exception as e:
            print(f"更新日時記録エラー: {e}")
    
    def _get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE country_code = %s
                    """, (f'hatena',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] or 0
                        }
                    return {'last_updated': None, 'data_count': 0}
        except Exception as e:
            print(f"キャッシュ情報取得エラー: {e}")
            return {'last_updated': None, 'data_count': 0}
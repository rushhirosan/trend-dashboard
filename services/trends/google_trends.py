import os
import re
from datetime import datetime
from database_config import TrendsCache
from dotenv import load_dotenv
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager
from trendspyg import download_google_trends_rss

# 環境変数を明示的に読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

class GoogleTrendsManager(BaseTrendsManager):
    """Google Trendsのトレンドを取得・管理するクラス（trendspyg使用）"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（trendspygはレート制限が緩いため、やや緩和）
        # 10リクエスト/分に設定（trendspygはRSS方式が高速で、レート制限が緩い）
        super().__init__(service_name='google', max_requests=10, window_seconds=60)
        
        logger.info(f"Google Trends Manager初期化完了 (trendspyg使用)")
    
    def _parse_traffic_to_score(self, traffic_str):
        """
        traffic文字列（例: "200+", "500+", "1M+"）を数値スコアに変換
        
        Args:
            traffic_str: trendspygから取得したtraffic文字列
            
        Returns:
            int: トラフィックに基づくスコア（0-100）
        """
        if not traffic_str or not isinstance(traffic_str, str):
            return 0
        
        # 数値と単位を抽出
        # 例: "200+", "500+", "1M+", "10K+"
        match = re.search(r'([\d.]+)([KMB]?)\+?', traffic_str.upper())
        if not match:
            return 0
        
        value = float(match.group(1))
        unit = match.group(2)
        
        # 単位を数値に変換
        multipliers = {
            'K': 1000,
            'M': 1000000,
            'B': 1000000000
        }
        
        if unit in multipliers:
            value = value * multipliers[unit]
        
        # スコアに変換（100万+ = 100点、10万+ = 50点、1万+ = 25点、1000+ = 10点）
        if value >= 1000000:
            return 100
        elif value >= 100000:
            return 50
        elif value >= 10000:
            return 25
        elif value >= 1000:
            return 10
        else:
            return 5
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す（regionなどの追加引数も受け取れるようにする）"""
        return 'google_trends'
    
    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            region = kwargs.get('region', 'JP')
            cached_data = self.db.get_google_trends_from_cache(region)
            
            # cached_dataがNoneの場合はデータベースエラー
            if cached_data is None:
                logger.error(f"❌ Google Trends: データベースからキャッシュを取得する際にエラーが発生しました")
                return None
            
            # キャッシュデータに検索URLを追加（存在しない場合のみ）
            if cached_data:
                for item in cached_data:
                    if 'google_search_url' not in item and 'keyword' in item:
                        keyword = item['keyword']
                        item['google_search_url'] = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
            
            return cached_data
        except Exception as e:
            logger.error(f"❌ Google Trends: キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.save_google_trends_to_cache(data, region)
        except Exception as e:
            logger.error(f"❌ Google Trends キャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.clear_google_trends_cache(region)
        except Exception as e:
            logger.error(f"❌ Google Trends キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新（regionなど追加引数を許容）"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Google Trends: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, region='JP', limit=20, *args, **kwargs):
        """外部APIからGoogle Trendsデータを取得（trendspyg使用）"""
        return self.get_trendspyg_data(region, limit)
    
    def get_trends(self, region='JP', limit=20, force_refresh=False):
        """Google Trendsを取得（キャッシュ優先、フォールバックでtrendspyg）"""
        # BaseTrendsManagerの共通処理を使用
        # auto_fetch_on_cache_miss=Trueで、キャッシュがない場合はtrendspygを呼び出す
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # trendspygを使用するため、キャッシュがない場合はAPIを呼び出す
            region=region
        )
        
        # regionパラメータを結果に追加
        if result and isinstance(result, dict):
            result['country'] = region
        return result
    
    def get_trendspyg_data(self, region='JP', limit=20):
        """trendspygを使用してGoogle Trendsデータを取得"""
        try:
            logger.info(f"=== Google Trends trendspyg取得開始 ===")
            logger.info(f"リクエストパラメータ: region={region}, limit={limit}")
            
            # レート制限チェック（必要に応じて自動待機）
            self.rate_limiter.wait_if_needed()
            
            # 国コードをtrendspygの形式に変換
            # trendspygはISO 3166-1 alpha-2国コードを使用（'JP', 'US'など）
            country_map = {
                'JP': 'JP',
                'US': 'US',
                'japan': 'JP',
                'united_states': 'US',
                'united states': 'US'
            }
            
            # regionを正規化
            region_upper = region.upper()
            geo_code = country_map.get(region_upper) or country_map.get(region.lower(), 'JP')
            logger.info(f"trendspyg国コード: {geo_code} (region={region})")
            
            # trendspygのRSS方式でトレンドを取得
            try:
                trends_list = download_google_trends_rss(geo=geo_code)
                
                if not trends_list or len(trends_list) == 0:
                    logger.warning(f"❌ Google Trends: {region}データが取得できませんでした（空の結果）")
                    return {
                        'success': False,
                        'error': f'{region}データが取得できませんでした',
                        'data': [],
                        'status': 'api_error',
                        'source': 'trendspyg',
                        'country': region
                    }
                
                logger.info(f"✅ trendspygから{len(trends_list)}件のデータを取得しました")
                
                # 取得可能な最大件数を確認（trendspygが返す全件数とlimitの小さい方）
                available_count = min(limit, len(trends_list))
                logger.info(f"📊 取得件数: {available_count}件 (limit={limit}, 取得可能={len(trends_list)}件)")
                
                # データを辞書形式に変換
                trends_data = []
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                for idx, trend_item in enumerate(trends_list[:limit]):
                    # trendspygのRSS出力形式からデータを抽出
                    keyword = trend_item.get('trend', '').strip()
                    
                    if not keyword:
                        continue
                    
                    # Google検索URLを生成
                    google_search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                    
                    # トラフィック情報を取得（存在する場合）
                    traffic = trend_item.get('traffic', '')
                    
                    # トラフィック情報からスコアを計算
                    traffic_score = self._parse_traffic_to_score(traffic)
                    
                    # ニュース記事の最初のURLを取得（存在する場合）
                    news_articles = trend_item.get('news_articles', [])
                    news_url = news_articles[0].get('url', '') if news_articles else ''
                    
                    # ランクに基づくスコアを計算（上位ほど高いスコア）
                    rank = idx + 1
                    rank_score = 100 - (rank - 1) * (100 / min(limit, len(trends_list)))
                    
                    # トラフィックスコアとランクスコアを組み合わせ（trafficが優先）
                    # traffic_scoreがある場合はそれを使用、ない場合はrank_scoreを使用
                    if traffic_score > 0:
                        score = traffic_score + (rank_score * 0.2)  # トラフィックスコアを優先、ランクで微調整
                    else:
                        score = rank_score  # trafficがない場合はrank_scoreを使用
                    
                    trends_data.append({
                        'keyword': keyword,
                        'rank': rank,
                        'popularity': score,
                        'score': score,
                        'country_code': region,
                        'refresh_date': current_date,
                        'google_search_url': google_search_url,
                        'traffic': traffic,
                        'traffic_score': traffic_score,  # トラフィックスコアも含める
                        'news_url': news_url
                    })
                    
                    # 最初の3件だけログ出力
                    if rank <= 3:
                        logger.debug(f"行 {rank}: keyword='{keyword}', traffic='{traffic}', traffic_score={traffic_score:.1f}, final_score={score:.1f}")
                
                logger.info(f"✅ Google Trends: {len(trends_data)}件のデータを変換しました (国コード: {region})")
                
                return {
                    'success': True,
                    'data': trends_data,
                    'status': 'success',
                    'source': 'trendspyg',
                    'country': region,
                    'actual_country': region,
                    'total_count': len(trends_data),
                    'refresh_date': current_date,
                    'data_date': current_date
                }
                
            except Exception as e:
                error_str = str(e)
                # 429エラー（レート制限）の検出
                if '429' in error_str or 'rate limit' in error_str.lower() or 'too many requests' in error_str.lower():
                    logger.error(f"❌ trendspyg API呼び出しエラー（レート制限）: {e}", exc_info=True)
                    return {
                        'success': False,
                        'error': f'レート制限に達しました。しばらく待ってから再試行してください: {str(e)}',
                        'data': [],
                        'status': 'rate_limited',
                        'source': 'trendspyg',
                        'country': region,
                        'debug_info': {
                            'error_type': type(e).__name__,
                            'error_message': str(e)
                        }
                    }
                else:
                    logger.error(f"❌ trendspyg API呼び出しエラー: {e}", exc_info=True)
                    return {
                        'success': False,
                        'error': f'trendspyg API呼び出しに失敗しました: {str(e)}',
                        'data': [],
                        'status': 'api_error',
                        'source': 'trendspyg',
                        'country': region,
                        'debug_info': {
                            'error_type': type(e).__name__,
                            'error_message': str(e)
                        }
                    }
            
        except Exception as e:
            logger.error(f"❌ Google Trends trendspyg取得エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Google Trends取得に失敗しました: {str(e)}',
                'data': [],
                'status': 'api_error',
                'source': 'trendspyg',
                'country': region,
                'debug_info': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            }
    


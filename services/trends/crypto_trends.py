"""
仮想通貨トレンド関連の処理を管理するモジュール
CoinGecko APIを使用してトレンド仮想通貨を取得
"""

import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class CryptoTrendsManager(BaseTrendsManager):
    """仮想通貨トレンドの管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='crypto', max_requests=10, window_seconds=60)
        
        self.base_url = "https://api.coingecko.com/api/v3"
        
        logger.info("Crypto Trends Manager初期化完了")
        logger.info(f"  Base URL: {self.base_url}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'crypto_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_crypto_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_crypto_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ Crypto キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_crypto_trends_cache()
        except Exception as e:
            logger.error(f"❌ Crypto キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Crypto: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """仮想通貨トレンドを取得（キャッシュ優先、market_cap_rankでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='market_cap_rank'で時価総額順でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='market_cap_rank',  # 時価総額順でソート
            sort_reverse=False  # 昇順（market_cap_rankが小さいほど上位）
        )
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """CoinGecko APIを使用して時価総額順の仮想通貨を取得"""
        try:
            logger.info(f"🪙 Crypto API呼び出し開始（時価総額順）")
            
            # CoinGeckoのmarketsエンドポイント（時価総額順）
            url = f"{self.base_url}/coins/markets"
            
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',  # 時価総額順
                'per_page': limit,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'  # 24時間変動率を含める
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'trends-dashboard/1.0.0'
            }
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ CoinGecko API エラー: HTTP {response.status_code}")
                return {
                    'success': False,
                    'error': f'CoinGecko API エラー: {response.status_code}',
                    'data': []
                }
            
            coins = response.json()
            
            if not coins or not isinstance(coins, list):
                logger.warning("⚠️ Crypto: データが取得できませんでした")
                return {
                    'success': False,
                    'error': '仮想通貨データが取得できませんでした',
                    'data': []
                }
            
            trends_data = []
            
            # 各コインの情報を組み立て
            for coin in coins:
                try:
                    coin_id = coin.get('id', '')
                    symbol = coin.get('symbol', '').upper()
                    name = coin.get('name', '')
                    market_cap_rank = coin.get('market_cap_rank', 0)
                    current_price = coin.get('current_price', 0)
                    price_change_24h = coin.get('price_change_24h', 0)
                    price_change_percentage_24h = coin.get('price_change_percentage_24h', 0)
                    market_cap = coin.get('market_cap', 0)
                    volume_24h = coin.get('total_volume', 0)
                    image_url = coin.get('image', '')
                    
                    # 価格データが取得できた場合のみ追加
                    if current_price > 0:
                        trends_data.append({
                            'coin_id': coin_id,
                            'symbol': symbol,
                            'name': name,
                            'market_cap_rank': market_cap_rank,
                            'search_score': 0,  # marketsエンドポイントにはsearch_scoreがないため0
                            'current_price': current_price,
                            'price_change_24h': price_change_24h,
                            'price_change_percentage_24h': price_change_percentage_24h,
                            'market_cap': market_cap,
                            'volume_24h': volume_24h,
                            'image_url': image_url,
                            'updated_at': datetime.now().isoformat()
                        })
                    else:
                        logger.debug(f"コイン {coin_id} ({symbol}): 価格データが取得できませんでした")
                    
                except Exception as e:
                    logger.debug(f"コイン {coin_id} 処理エラー: {e}")
                    continue
            
            if not trends_data:
                logger.warning("⚠️ Crypto: データが取得できませんでした")
                return {
                    'success': False,
                    'error': '仮想通貨データが取得できませんでした',
                    'data': []
                }
            
            # 時価総額順で既にソートされているが、念のためmarket_cap_rankでソート
            trends_data.sort(key=lambda x: x.get('market_cap_rank', 999999))
            
            # ランキングを設定（時価総額順）
            for i, item in enumerate(trends_data, 1):
                item['rank'] = i
            
            logger.info(f"✅ Crypto: {len(trends_data)}件のデータを取得しました（時価総額順）")
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'CoinGecko API (Market Cap)',
                'total_count': len(trends_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Crypto API エラー: {e}", exc_info=True)
            return {
                'error': f'仮想通貨データ取得エラー: {str(e)}',
                'success': False
            }
    
    def _get_coins_prices(self, coin_ids):
        """複数のコインの価格情報を一度に取得"""
        try:
            url = f"{self.base_url}/simple/price"
            # コインIDをカンマ区切りで結合（CoinGecko APIは複数IDをサポート）
            ids_string = ','.join(coin_ids)
            params = {
                'ids': ids_string,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                prices = {}
                for coin_id in coin_ids:
                    coin_data = data.get(coin_id, {})
                    if coin_data:
                        prices[coin_id] = {
                            'current_price': coin_data.get('usd', 0),
                            'price_change_24h': coin_data.get('usd_24h_change', 0),
                            'price_change_percentage_24h': coin_data.get('usd_24h_change', 0),
                            'market_cap': coin_data.get('usd_market_cap', 0),
                            'total_volume': coin_data.get('usd_24h_vol', 0)
                        }
                    else:
                        prices[coin_id] = {}
                return prices
            else:
                logger.warning(f"コイン価格一括取得エラー: HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"コイン価格一括取得エラー: {e}", exc_info=True)
            return {}
    
    def _get_coin_price(self, coin_id):
        """個別のコイン価格情報を取得（後方互換性のため残す）"""
        prices = self._get_coins_prices([coin_id])
        return prices.get(coin_id, {})

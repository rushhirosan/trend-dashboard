import requests
import json
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

class CISAKEVTrendsManager(BaseTrendsManager):
    """CISA KEV（Known Exploited Vulnerabilities）トレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='cisa_kev', max_requests=10, window_seconds=60)
        
        # CISA KEV JSON API URL（GitHubから直接取得）
        self.kev_json_url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        # GitHubのraw URL（フォールバック用）
        self.github_kev_url = "https://raw.githubusercontent.com/cisagov/kev-data/main/data/vulnerabilities.json"
        
        logger.info("CISA KEV Trends Manager初期化:")
        logger.info(f"  KEV JSON URL: {self.kev_json_url}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'cisa_kev_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_cisa_kev_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_cisa_kev_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ CISA KEV キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_cisa_kev_trends_cache()
        except Exception as e:
            logger.error(f"❌ CISA KEV キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ CISA KEV: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """CISA KEVトレンドを取得（キャッシュ優先、date_addedでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='date_added'で公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='date_added',  # 公開日でソート
            sort_reverse=True  # 降順（新しい順）
        )
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """CISA KEVデータを取得（最近更新されたものから25件）"""
        try:
            logger.info(f"CISA KEV API呼び出し開始")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # まず公式サイトのJSONを試す
            response = requests.get(self.kev_json_url, timeout=15)
            
            if response.status_code != 200:
                # フォールバック: GitHubのraw URLを試す
                logger.warning(f"⚠️ CISA公式サイトから取得失敗 (HTTP {response.status_code})。GitHubを試します")
                self.rate_limiter.wait_if_needed()
                response = requests.get(self.github_kev_url, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"❌ CISA KEV API エラー: HTTP {response.status_code}")
                return {
                    'error': f'CISA KEV API エラー: {response.status_code}',
                    'success': False
                }
            
            data = response.json()
            
            # KEVデータの構造を確認
            # 通常は {"vulnerabilities": [...]} の形式
            vulnerabilities = data.get('vulnerabilities', [])
            if not vulnerabilities:
                # フォールバック: 直接リストの場合
                if isinstance(data, list):
                    vulnerabilities = data
                else:
                    logger.error("❌ CISA KEV: データ構造が予期しない形式です")
                    return {
                        'error': 'CISA KEVデータの構造が予期しない形式です',
                        'success': False
                    }
            
            logger.info(f"✅ CISA KEV: {len(vulnerabilities)}件の脆弱性データを取得")
            
            # データを整形
            formatted_data = []
            for vuln in vulnerabilities:
                try:
                    # dateAddedをパース（最近更新されたものを優先）
                    date_added = vuln.get('dateAdded', '')
                    date_required = vuln.get('dateRequired', '')
                    due_date = vuln.get('dueDate', '')
                    
                    # 日付でソートするため、dateAddedを使用（なければdateRequired）
                    sort_date = date_added or date_required or ''
                    
                    formatted_item = {
                        'cve_id': vuln.get('cveID', ''),
                        'vendor_project': vuln.get('vendorProject', ''),
                        'product': vuln.get('product', ''),
                        'vulnerability_name': vuln.get('vulnerabilityName', ''),
                        'date_added': date_added,
                        'date_required': date_required,
                        'due_date': due_date,
                        'short_description': vuln.get('shortDescription', ''),
                        'required_action': vuln.get('requiredAction', ''),
                        'notes': vuln.get('notes', ''),
                        'sort_date': sort_date  # ソート用
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ CISA KEV アイテムパースエラー: {e}")
                    continue
            
            # 日付でソート（新しい順）
            formatted_data.sort(key=lambda x: x.get('sort_date') or '', reverse=True)
            
            # 制限数まで取得（最近更新されたものから）
            formatted_data = formatted_data[:limit]
            
            # ランキングを設定
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
                # ソート用フィールドを削除
                item.pop('sort_date', None)
            
            logger.info(f"✅ CISA KEV: {len(formatted_data)}件の最新脆弱性情報を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'cisa_kev_api',
                'total_count': len(formatted_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ CISA KEV API タイムアウトエラー", exc_info=True)
            return {
                'error': 'CISA KEV API タイムアウト',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ CISA KEV API エラー: {e}", exc_info=True)
            return {
                'error': f'CISA KEVデータ取得エラー: {str(e)}',
                'success': False
            }

import requests
import json
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

class CISAKEVTrendsManager:
    """CISA KEV（Known Exploited Vulnerabilities）トレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        # CISA KEV JSON API URL（GitHubから直接取得）
        self.kev_json_url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        # GitHubのraw URL（フォールバック用）
        self.github_kev_url = "https://raw.githubusercontent.com/cisagov/kev-data/main/data/vulnerabilities.json"
        self.db = TrendsCache()
        # レート制限: CISA APIは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('cisa_kev', max_requests=10, window_seconds=60)
        
        logger.info("CISA KEV Trends Manager初期化:")
        logger.info(f"  KEV JSON URL: {self.kev_json_url}")
    
    def get_trends(self, limit=25, force_refresh=False):
        """CISA KEVトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 CISA KEV force_refresh: キャッシュをクリアします")
                self.db.clear_cisa_kev_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_cisa_kev_trends_from_cache()
            
            if cached_data:
                # 公開日でソート（新しい順）
                cached_data.sort(key=lambda x: x.get('date_added') or '', reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                # キャッシュデータを使用する場合でも、cache_statusを更新
                if force_refresh:
                    try:
                        self.db.update_cache_status('cisa_kev_trends', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ CISA KEV: cache_status更新エラー（処理は継続）: {e}")
                
                logger.info(f"✅ CISA KEV: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ CISA KEV: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ CISA KEV: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_kev_trends(limit)
                
        except Exception as e:
            logger.error(f"❌ CISA KEV トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'CISA KEVトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_kev_trends(self, limit=25):
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
            
            # キャッシュに保存
            if formatted_data:
                self.db.save_cisa_kev_trends_to_cache(formatted_data)
                self.db.update_cache_status('cisa_kev_trends', len(formatted_data))
            
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


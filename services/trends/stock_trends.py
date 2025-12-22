"""
株価トレンド関連の処理を管理するモジュール
yfinanceを使用して急騰・急落銘柄を取得
"""

import os
import yfinance as yf
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class StockTrendsManager:
    """株価トレンドの管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.db = TrendsCache()
        # レート制限: yfinanceは制限が緩いが、保守的に20リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('stock', max_requests=20, window_seconds=60)
        
        # 日本株と米国株の主要銘柄リスト
        # 日本株: 東証プライム上場の主要銘柄（50銘柄に拡張）
        self.jp_tickers = [
            '7203.T',  # トヨタ
            '6758.T',  # ソニー
            '9984.T',  # ソフトバンクG
            '6861.T',  # キーエンス
            '6098.T',  # リクルート
            '6752.T',  # パナソニック
            '8035.T',  # 東京エレクトロン
            '8306.T',  # 三菱UFJ
            '8411.T',  # みずほFG
            '9434.T',  # ソフトバンク
            '8058.T',  # 三菱商事
            '4063.T',  # 信越化学
            '4503.T',  # アステラス製薬
            '4519.T',  # 中外製薬
            '6367.T',  # ダイキン
            '6501.T',  # 日立製作所
            '6503.T',  # 三菱電機
            '7732.T',  # トプコン
            '4901.T',  # 富士フイルム
            '7733.T',  # オリンパス
            '9983.T',  # ファーストリテイリング
            '7974.T',  # 任天堂
            '7267.T',  # ホンダ
            '4061.T',  # デンカ
            '4568.T',  # 第一三共
            '6954.T',  # ファナック
            '6594.T',  # 日本電産
            '8001.T',  # 伊藤忠商事
            '8002.T',  # 丸紅
            '2914.T',  # 日本たばこ産業
            '3407.T',  # 旭化成
            '3405.T',  # クラレ
            '3401.T',  # 帝人
            '3402.T',  # 東レ
            '3407.T',  # 旭化成
            '4452.T',  # 花王
            '4911.T',  # 資生堂
            '5108.T',  # ブリヂストン
            '5101.T',  # 横浜ゴム
            '5713.T',  # 住友金属鉱山
            '5714.T',  # DOWAホールディングス
            '5801.T',  # 古河電気工業
            '5802.T',  # 住友電気工業
            '5803.T',  # フジクラ
            '6113.T',  # アマダ
            '6134.T',  # FUJI
            '6136.T',  # オーエスジー
            '6301.T',  # コマツ
            '6302.T',  # 住友重機械工業
            '6305.T',  # 日立建機
        ]
        
        # 米国株: S&P500の主要銘柄（50銘柄に拡張）
        self.us_tickers = [
            'AAPL',   # Apple
            'MSFT',   # Microsoft
            'GOOGL',  # Google
            'AMZN',   # Amazon
            'NVDA',   # NVIDIA
            'META',   # Meta
            'TSLA',   # Tesla
            'BRK-B',  # Berkshire Hathaway
            'V',      # Visa
            'JNJ',    # Johnson & Johnson
            'WMT',    # Walmart
            'JPM',    # JPMorgan Chase
            'MA',     # Mastercard
            'PG',     # Procter & Gamble
            'UNH',    # UnitedHealth
            'HD',     # Home Depot
            'DIS',    # Disney
            'BAC',    # Bank of America
            'ADBE',   # Adobe
            'NFLX',   # Netflix
            'AVGO',   # Broadcom
            'COST',   # Costco
            'NKE',    # Nike
            'CRM',    # Salesforce
            'AMD',    # AMD
            'INTC',   # Intel
            'CSCO',   # Cisco
            'PEP',    # PepsiCo
            'TMO',    # Thermo Fisher Scientific
            'ABBV',   # AbbVie
            'ACN',    # Accenture
            'DHR',    # Danaher
            'VZ',     # Verizon
            'CMCSA',  # Comcast
            'NFLX',   # Netflix
            'LIN',    # Linde
            'TXN',    # Texas Instruments
            'AMGN',   # Amgen
            'HON',    # Honeywell
            'QCOM',   # Qualcomm
            'INTU',   # Intuit
            'ISRG',   # Intuitive Surgical
            'GILD',   # Gilead Sciences
            'AMAT',   # Applied Materials
            'BKNG',   # Booking Holdings
            'ADI',    # Analog Devices
            'CDNS',   # Cadence Design Systems
            'SNPS',   # Synopsys
            'KLAC',   # KLA Corporation
            'FTNT',   # Fortinet
        ]
        
        logger.info("Stock Trends Manager初期化完了")
    
    def get_trends(self, market='US', limit=25, force_refresh=False):
        """
        株価トレンドを取得（急騰・急落銘柄）
        
        Args:
            market: 'JP' (日本株) または 'US' (米国株)
            limit: 取得件数
            force_refresh: キャッシュを無視して強制更新
        
        Returns:
            dict: トレンドデータ
        """
        try:
            if force_refresh:
                logger.info(f"🔄 Stock force_refresh: キャッシュをクリアします (market: {market})")
                self.db.clear_stock_trends_cache(market)
            
            # キャッシュからデータを取得
            cached_data = self.db.get_stock_trends_from_cache(market)
            
            if cached_data:
                # 変動率でソート（降順）
                cached_data.sort(key=lambda x: abs(x.get('change_percent', 0)), reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                logger.info(f"✅ Stock: キャッシュから{len(cached_data)}件のデータを取得しました (market: {market})")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'market': market
                }
            else:
                # キャッシュデータがない場合
                # Stock/Cryptoは無料APIのため、スケジューラー実行時（force_refresh=false）でもキャッシュがない場合はAPIを呼び出す
                # これにより、14時のスケジューラー実行時にもデータが取得できる
                if not force_refresh:
                    logger.info(f"📈 Stock: キャッシュデータが見つかりません (market: {market})。スケジューラー実行時のため、外部APIを呼び出します")
                    result = self._fetch_trending_stocks(market, limit)
                    # データが取得できた場合のみログに記録
                    if result.get('success') and result.get('data'):
                        logger.info(f"✅ Stock: スケジューラー実行時に{len(result.get('data', []))}件のデータを取得しました (market: {market})")
                    else:
                        logger.warning(f"⚠️ Stock: スケジューラー実行時にデータが取得できませんでした (market: {market}, status: {result.get('status')})")
                    return result
                # force_refresh=trueの場合も外部APIを呼び出す
                logger.warning(f"⚠️ Stock: キャッシュデータが見つかりません。外部APIを呼び出します (market: {market})")
                return self._fetch_trending_stocks(market, limit)
                
        except Exception as e:
            logger.error(f"❌ Stock トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'株価トレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_trending_stocks(self, market='US', limit=25):
        """yfinanceを使用して急騰・急落銘柄を取得"""
        try:
            logger.info(f"📈 Stock API呼び出し開始 (market: {market})")
            
            # 市場に応じた銘柄リストを選択
            tickers = self.jp_tickers if market == 'JP' else self.us_tickers
            
            # 過去1日のデータを取得
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)  # 2日前から（週末考慮）
            
            trends_data = []
            
            # 各銘柄を個別に取得（yfinanceは個別取得が安定）
            # fly.io環境でのタイムアウト対策: 最大20銘柄までに制限（処理時間短縮）
            max_tickers = min(len(tickers), 20)
            success_count = 0
            error_count = 0
            empty_count = 0
            
            logger.info(f"📈 Stock: {max_tickers}銘柄のデータ取得を開始します (market: {market})")
            
            for ticker_symbol in tickers[:max_tickers]:
                try:
                    # レート制限をチェック（各銘柄取得前に）
                    self.rate_limiter.wait_if_needed()
                    
                    ticker = yf.Ticker(ticker_symbol)
                    # history取得（タイムアウト対策: エラーが発生した場合はスキップ）
                    # 週末や市場が閉まっている場合を考慮して、5日間のデータを取得（最後の取引日を特定するため）
                    try:
                        hist = ticker.history(period='5d', timeout=10)  # タイムアウトを10秒に延長
                    except Exception as e:
                        logger.warning(f"銘柄 {ticker_symbol} history取得エラー: {e}")
                        error_count += 1
                        continue
                    
                    if hist.empty:
                        logger.warning(f"銘柄 {ticker_symbol}: データが空です（市場が閉まっている可能性があります）")
                        empty_count += 1
                        continue
                    
                    logger.debug(f"銘柄 {ticker_symbol}: {len(hist)}日分のデータを取得しました")
                    success_count += 1
                    
                    # データが1日分しかない場合（週末や市場が閉まっている場合）
                    if len(hist) < 2:
                        # 最後の取引日のデータを使用（変動率は0として扱う）
                        current_price = hist['Close'].iloc[-1]
                        previous_price = current_price  # 同じ価格として扱う
                        change = 0
                        change_percent = 0
                        logger.info(f"銘柄 {ticker_symbol}: データが1日分のみ（市場が閉まっている可能性があります）- 最後の取引日データを使用")
                    else:
                        # 通常通り、最新と前日のデータを使用
                        current_price = hist['Close'].iloc[-1]
                        previous_price = hist['Close'].iloc[-2]
                        change = current_price - previous_price
                        change_percent = (change / previous_price) * 100 if previous_price > 0 else 0
                    
                    volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0
                    
                    # 銘柄情報を取得（エラーハンドリング付き、タイムアウト対策）
                    company_name = ticker_symbol
                    market_cap = 0
                    try:
                        # info取得はオプション（タイムアウトしやすいため、失敗しても続行）
                        info = ticker.info
                        company_name = info.get('longName') or info.get('shortName') or ticker_symbol
                        market_cap = info.get('marketCap', 0)
                    except Exception:
                        # info取得に失敗した場合はシンボル名を使用
                        pass
                    
                    trends_data.append({
                        'symbol': ticker_symbol,
                        'name': company_name,
                        'current_price': float(current_price),
                        'previous_price': float(previous_price),
                        'change': float(change),
                        'change_percent': round(change_percent, 2),
                        'volume': int(volume),
                        'market_cap': market_cap,
                        'market': market,
                        'updated_at': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.debug(f"銘柄 {ticker_symbol} 取得エラー: {e}")
                    continue
            
            if not trends_data:
                logger.warning(f"⚠️ Stock: データが取得できませんでした (market: {market}, tickers数: {len(tickers[:max_tickers])})")
                logger.warning(f"⚠️ Stock: これは週末・市場休場時、またはyfinance APIの問題の可能性があります")
                # データが取得できなかった場合でも、空のデータを返す（エラーではなく空の結果として扱う）
                # ただし、キャッシュには保存しない（次回の実行時に再試行するため）
                return {
                    'success': True,  # エラーではなく、データがない状態として扱う
                    'data': [],
                    'status': 'no_data',
                    'source': 'yfinance',
                    'market': market,
                    'message': '株価データが取得できませんでした（市場が閉まっている可能性があります）'
                }
            
            # 変動率の絶対値でソート（急騰・急落順）
            trends_data.sort(key=lambda x: abs(x.get('change_percent', 0)), reverse=True)
            
            # ランキングを設定
            for i, item in enumerate(trends_data, 1):
                item['rank'] = i
            
            # 制限数まで取得
            trends_data = trends_data[:limit]
            
            # キャッシュに保存
            self.db.save_stock_trends_to_cache(trends_data, market)
            logger.info(f"✅ Stock: {len(trends_data)}件のデータを取得し、キャッシュに保存しました (market: {market})")
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'yfinance',
                'market': market,
                'total_count': len(trends_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Stock API エラー: {e}", exc_info=True)
            return {
                'error': f'株価データ取得エラー: {str(e)}',
                'success': False
            }

"""
株価トレンド関連の処理を管理するモジュール
yfinanceを使用して急騰・急落銘柄を取得
"""

import os
import yfinance as yf
from yahooquery import Ticker as YahooTicker
import requests
import time
import pandas as pd
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
        # レート制限: yfinanceは制限が緩いが、保守的に10リクエスト/分に設定（APIの安定性を考慮）
        self.rate_limiter = get_rate_limiter('stock', max_requests=10, window_seconds=60)
        
        # yfinanceのセッション設定（Fly.io環境での接続問題を回避するため）
        # ユーザーエージェントを設定して、より安定した接続を試みる
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # yahooqueryを使用するかどうかのフラグ（環境変数で制御可能、デフォルトはtrue）
        self.use_yahooquery = os.getenv('USE_YAHOOQUERY', 'true').lower() == 'true'
        
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
            '7201.T',  # 日産自動車
            '7269.T',  # スズキ
            '7270.T',  # スバル
            '7831.T',  # ウィルコム沖縄
            '7832.T',  # バンダイナムコホールディングス
            '8005.T',  # スクウェア・エニックス・ホールディングス
            '8053.T',  # 住友商事
            '8056.T',  # 日本ユニシス
            '8308.T',  # りそなホールディングス
            '8316.T',  # 三井住友フィナンシャルグループ
            '8601.T',  # 大和証券グループ本社
            '8604.T',  # 野村ホールディングス
            '8801.T',  # 三井不動産
            '8802.T',  # 三菱地所
            '8830.T',  # 住友不動産
        ]
        
        # ティッカーシンボルから会社名へのマッピング（API呼び出しを避けるため）
        self.jp_ticker_names = {
            '7203.T': 'トヨタ自動車',
            '6758.T': 'ソニーグループ',
            '9984.T': 'ソフトバンクグループ',
            '6861.T': 'キーエンス',
            '6098.T': 'リクルートホールディングス',
            '6752.T': 'パナソニックホールディングス',
            '8035.T': '東京エレクトロン',
            '8306.T': '三菱UFJフィナンシャル・グループ',
            '8411.T': 'みずほフィナンシャルグループ',
            '9434.T': 'ソフトバンク',
            '8058.T': '三菱商事',
            '4063.T': '信越化学工業',
            '4503.T': 'アステラス製薬',
            '4519.T': '中外製薬',
            '6367.T': 'ダイキン工業',
            '6501.T': '日立製作所',
            '6503.T': '三菱電機',
            '7732.T': 'トプコン',
            '4901.T': '富士フイルムホールディングス',
            '7733.T': 'オリンパス',
            '9983.T': 'ファーストリテイリング',
            '7974.T': '任天堂',
            '7267.T': 'ホンダ',
            '4061.T': 'デンカ',
            '4568.T': '第一三共',
            '6954.T': 'ファナック',
            '6594.T': '日本電産',
            '8001.T': '伊藤忠商事',
            '8002.T': '丸紅',
            '2914.T': '日本たばこ産業',
            '3407.T': '旭化成',
            '3405.T': 'クラレ',
            '3401.T': '帝人',
            '3402.T': '東レ',
            '4452.T': '花王',
            '4911.T': '資生堂',
            '5108.T': 'ブリヂストン',
            '5101.T': '横浜ゴム',
            '5713.T': '住友金属鉱山',
            '5714.T': 'DOWAホールディングス',
            '5801.T': '古河電気工業',
            '5802.T': '住友電気工業',
            '5803.T': 'フジクラ',
            '6113.T': 'アマダ',
            '6134.T': 'FUJI',
            '6136.T': 'オーエスジー',
            '6301.T': 'コマツ',
            '6302.T': '住友重機械工業',
            '6305.T': '日立建機',
            '7201.T': '日産自動車',
            '7269.T': 'スズキ',
            '7270.T': 'スバル',
            '7831.T': 'ウィルコム沖縄',
            '7832.T': 'バンダイナムコホールディングス',
            '8005.T': 'スクウェア・エニックス・ホールディングス',
            '8053.T': '住友商事',
            '8056.T': '日本ユニシス',
            '8308.T': 'りそなホールディングス',
            '8316.T': '三井住友フィナンシャルグループ',
            '8601.T': '大和証券グループ本社',
            '8604.T': '野村ホールディングス',
            '8801.T': '三井不動産',
            '8802.T': '三菱地所',
            '8830.T': '住友不動産',
        }
        
        # 米国株: S&P500の主要銘柄（60銘柄に拡張）
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
            'MRVL',   # Marvell Technology
            'MU',     # Micron Technology
            'LRCX',   # Lam Research
            'NXPI',   # NXP Semiconductors
            'ON',     # ON Semiconductor
            'MCHP',   # Microchip Technology
            'SWKS',   # Skyworks Solutions
            'QRVO',   # Qorvo
            'MPWR',   # Monolithic Power Systems
            'CRWD',   # CrowdStrike
            'PANW',   # Palo Alto Networks
            'ZS',     # Zscaler
        ]
        
        # 米国株のティッカーシンボルから会社名へのマッピング
        self.us_ticker_names = {
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Alphabet (Google)',
            'AMZN': 'Amazon',
            'NVDA': 'NVIDIA',
            'META': 'Meta Platforms',
            'TSLA': 'Tesla',
            'BRK-B': 'Berkshire Hathaway',
            'V': 'Visa',
            'JNJ': 'Johnson & Johnson',
            'WMT': 'Walmart',
            'JPM': 'JPMorgan Chase',
            'MA': 'Mastercard',
            'PG': 'Procter & Gamble',
            'UNH': 'UnitedHealth Group',
            'HD': 'Home Depot',
            'DIS': 'Walt Disney',
            'BAC': 'Bank of America',
            'ADBE': 'Adobe',
            'NFLX': 'Netflix',
            'AVGO': 'Broadcom',
            'COST': 'Costco Wholesale',
            'NKE': 'Nike',
            'CRM': 'Salesforce',
            'AMD': 'Advanced Micro Devices',
            'INTC': 'Intel',
            'CSCO': 'Cisco Systems',
            'PEP': 'PepsiCo',
            'TMO': 'Thermo Fisher Scientific',
            'ABBV': 'AbbVie',
            'ACN': 'Accenture',
            'DHR': 'Danaher',
            'VZ': 'Verizon',
            'CMCSA': 'Comcast',
            'LIN': 'Linde',
            'TXN': 'Texas Instruments',
            'AMGN': 'Amgen',
            'HON': 'Honeywell',
            'QCOM': 'Qualcomm',
            'INTU': 'Intuit',
            'ISRG': 'Intuitive Surgical',
            'GILD': 'Gilead Sciences',
            'AMAT': 'Applied Materials',
            'BKNG': 'Booking Holdings',
            'ADI': 'Analog Devices',
            'CDNS': 'Cadence Design Systems',
            'SNPS': 'Synopsys',
            'KLAC': 'KLA Corporation',
            'FTNT': 'Fortinet',
        }
        
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
                
                # レスポンス時はlimitで制限
                return_data = cached_data[:limit]
                
                logger.info(f"✅ Stock: キャッシュから{len(cached_data)}件のデータを取得しました (market: {market}, 返却: {len(return_data)}件)")
                return {
                    'success': True,
                    'data': return_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'market': market,
                    'total_count': len(cached_data)  # キャッシュの全件数を返す
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
        """yahooqueryまたはyfinanceを使用して急騰・急落銘柄を取得"""
        # yahooqueryを使用する場合
        if self.use_yahooquery:
            return self._fetch_trending_stocks_yahooquery(market, limit)
        
        # yfinanceを使用する場合（従来の方法）
        return self._fetch_trending_stocks_yfinance(market, limit)
    
    def _fetch_trending_stocks_yahooquery(self, market='US', limit=25):
        """yahooqueryを使用して急騰・急落銘柄を取得（Fly.io環境での接続問題を回避）"""
        try:
            logger.info(f"📈 Stock API呼び出し開始 (yahooquery使用, market: {market})")
            
            # 市場に応じた銘柄リストを選択
            tickers = self.jp_tickers if market == 'JP' else self.us_tickers
            
            # 最大60銘柄まで取得（より多くの銘柄から騰落率の大きいものを選べるように）
            max_tickers = min(len(tickers), 60)
            ticker_symbols = tickers[:max_tickers]
            
            logger.info(f"📈 Stock: {max_tickers}銘柄のデータ取得を開始します (market: {market})")
            
            # yahooqueryで一括取得（効率的）
            try:
                yahoo_ticker = YahooTicker(ticker_symbols)
                hist = yahoo_ticker.history(period='5d')
                
                if hist.empty:
                    logger.warning(f"⚠️ Stock: データが取得できませんでした (market: {market})")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'no_data',
                        'source': 'yahooquery',
                        'market': market,
                        'message': '株価データが取得できませんでした'
                    }
                
                trends_data = []
                success_count = 0
                error_count = 0
                
                # 各銘柄のデータを処理
                for ticker_symbol in ticker_symbols:
                    try:
                        # MultiIndexから該当銘柄のデータを抽出
                        if isinstance(hist.index, pd.MultiIndex):
                            try:
                                ticker_data = hist.xs(ticker_symbol, level='symbol')
                            except KeyError:
                                # 銘柄がデータに含まれていない場合
                                logger.warning(f"銘柄 {ticker_symbol}: データが見つかりません")
                                error_count += 1
                                continue
                        else:
                            # 単一銘柄の場合はそのまま使用
                            ticker_data = hist
                        
                        if ticker_data.empty or len(ticker_data) < 1:
                            error_count += 1
                            continue
                        
                        # データが1日分しかない場合
                        if len(ticker_data) < 2:
                            current_price = float(ticker_data['close'].iloc[-1])
                            previous_price = current_price
                            change = 0
                            change_percent = 0
                        else:
                            # 通常通り、最新と前日のデータを使用
                            current_price = float(ticker_data['close'].iloc[-1])
                            previous_price = float(ticker_data['close'].iloc[-2])
                            change = current_price - previous_price
                            change_percent = (change / previous_price) * 100 if previous_price > 0 else 0
                        
                        volume = int(ticker_data['volume'].iloc[-1]) if 'volume' in ticker_data.columns else 0
                        
                        # 会社名を取得
                        if market == 'JP':
                            company_name = self.jp_ticker_names.get(ticker_symbol, ticker_symbol)
                        else:
                            company_name = self.us_ticker_names.get(ticker_symbol, ticker_symbol)
                        
                        trends_data.append({
                            'symbol': ticker_symbol,
                            'name': company_name,
                            'current_price': current_price,
                            'previous_price': previous_price,
                            'change': change,
                            'change_percent': round(change_percent, 2),
                            'volume': volume,
                            'market_cap': 0,
                            'market': market,
                            'updated_at': datetime.now().isoformat()
                        })
                        success_count += 1
                        
                    except Exception as e:
                        logger.warning(f"銘柄 {ticker_symbol} 処理エラー: {str(e)[:100]}")
                        error_count += 1
                        continue
                
                if not trends_data:
                    logger.warning(f"⚠️ Stock: データが取得できませんでした (market: {market}, 成功: {success_count}, エラー: {error_count})")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'no_data',
                        'source': 'yahooquery',
                        'market': market,
                        'message': '株価データが取得できませんでした'
                    }
                
                # 変動率の絶対値でソート（急騰・急落順）
                trends_data.sort(key=lambda x: abs(x.get('change_percent', 0)), reverse=True)
                
                # ランキングを設定
                for i, item in enumerate(trends_data, 1):
                    item['rank'] = i
                
                # キャッシュには全データを保存
                self.db.save_stock_trends_to_cache(trends_data, market)
                logger.info(f"✅ Stock: {len(trends_data)}件のデータを取得し、キャッシュに保存しました (market: {market}, 成功: {success_count}, エラー: {error_count})")
                
                # レスポンス時はlimitで制限
                return_data = trends_data[:limit]
                
                return {
                    'success': True,
                    'data': return_data,
                    'status': 'api_fetched',
                    'source': 'yahooquery',
                    'market': market,
                    'total_count': len(trends_data)
                }
                
            except Exception as e:
                logger.error(f"❌ Stock yahooquery API エラー: {e}", exc_info=True)
                return {
                    'error': f'株価データ取得エラー: {str(e)}',
                    'success': False
                }
                
        except Exception as e:
            logger.error(f"❌ Stock yahooquery エラー: {e}", exc_info=True)
            return {
                'error': f'株価データ取得エラー: {str(e)}',
                'success': False
            }
    
    def _fetch_trending_stocks_yfinance(self, market='US', limit=25):
        """yfinanceを使用して急騰・急落銘柄を取得（従来の方法）"""
        try:
            logger.info(f"📈 Stock API呼び出し開始 (yfinance使用, market: {market})")
            
            # 市場に応じた銘柄リストを選択
            tickers = self.jp_tickers if market == 'JP' else self.us_tickers
            
            # 過去1日のデータを取得
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)  # 2日前から（週末考慮）
            
            trends_data = []
            
            # 各銘柄を個別に取得（yfinanceは個別取得が安定）
            # fly.io環境でのタイムアウト対策: 最大60銘柄までに制限（処理時間短縮）
            # タイムアウトを8秒、リトライロジック追加、info取得削除により高速化
            max_tickers = min(len(tickers), 60)
            success_count = 0
            error_count = 0
            empty_count = 0
            
            logger.info(f"📈 Stock: {max_tickers}銘柄のデータ取得を開始します (market: {market})")
            
            for ticker_symbol in tickers[:max_tickers]:
                try:
                    # レート制限をチェック（各銘柄取得前に）
                    self.rate_limiter.wait_if_needed()
                    
                    # 各銘柄の取得開始をログに記録
                    logger.debug(f"📈 銘柄 {ticker_symbol} のデータ取得を開始します")
                    
                    # カスタムセッションを使用してTickerを作成（Fly.io環境での接続問題を回避）
                    ticker = yf.Ticker(ticker_symbol, session=self.session)
                    # history取得（タイムアウト対策: エラーが発生した場合はスキップ）
                    # 週末や市場が閉まっている場合を考慮して、5日間のデータを取得（最後の取引日を特定するため）
                    hist = None
                    max_retries = 5  # リトライ回数を5回に増加（yfinance APIの不安定性を考慮）
                    retry_delay = 3  # 初期待機時間を3秒に延長（yfinance APIの復旧を待つ）
                    
                    for retry in range(max_retries):
                        try:
                            # タイムアウトを10秒に延長（Fly.io環境でのネットワーク遅延を考慮）
                            hist = ticker.history(period='5d', timeout=10)
                            if hist is not None and not hist.empty:
                                break  # 成功したらループを抜ける
                            else:
                                # データが空の場合はリトライ
                                if retry < max_retries - 1:
                                    logger.warning(f"銘柄 {ticker_symbol}: データが空です (リトライ {retry + 1}/{max_retries})")
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # 指数バックオフ
                                else:
                                    logger.warning(f"銘柄 {ticker_symbol}: データが空です（全リトライ失敗）")
                                    empty_count += 1
                                    hist = None
                                    break
                        except Exception as e:
                            error_msg = str(e)
                            # JSONパースエラーの場合は、より長い待機時間を設定
                            if 'Expecting value' in error_msg or 'JSON' in error_msg:
                                if retry < max_retries - 1:
                                    wait_time = retry_delay * (retry + 2)  # より長い待機時間
                                    logger.warning(f"銘柄 {ticker_symbol} JSONパースエラー (リトライ {retry + 1}/{max_retries}, {wait_time}秒待機): {error_msg[:100]}")
                                    time.sleep(wait_time)
                                    retry_delay *= 2
                                else:
                                    logger.warning(f"銘柄 {ticker_symbol} JSONパースエラー (全リトライ失敗): {error_msg[:100]}")
                                    error_count += 1
                                    hist = None
                            else:
                                if retry < max_retries - 1:
                                    logger.warning(f"銘柄 {ticker_symbol} history取得エラー (リトライ {retry + 1}/{max_retries}): {error_msg[:100]}")
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # 指数バックオフ
                                else:
                                    logger.warning(f"銘柄 {ticker_symbol} history取得エラー (全リトライ失敗): {error_msg[:100]}")
                                    error_count += 1
                                    hist = None
                    
                    if hist is None:
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
                    
                    # 銘柄情報を取得（マッピング辞書から会社名を取得）
                    # API呼び出しを避けるため、マッピング辞書を使用
                    if market == 'JP':
                        company_name = self.jp_ticker_names.get(ticker_symbol, ticker_symbol)
                    else:
                        company_name = self.us_ticker_names.get(ticker_symbol, ticker_symbol)
                    market_cap = 0
                    
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
            
            # 取得結果をログに出力
            logger.info(f"📊 Stock: データ取得結果 (market: {market})")
            logger.info(f"  成功: {success_count}件, エラー: {error_count}件, 空データ: {empty_count}件, 合計: {len(trends_data)}件")
            
            if not trends_data:
                logger.warning(f"⚠️ Stock: データが取得できませんでした (market: {market}, tickers数: {len(tickers[:max_tickers])})")
                logger.warning(f"⚠️ Stock: 成功: {success_count}件, エラー: {error_count}件, 空データ: {empty_count}件")
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
            
            # キャッシュには全データを保存（limitで制限しない）
            # これにより、異なるlimitパラメータで呼び出されても、キャッシュから適切な件数を返せる
            self.db.save_stock_trends_to_cache(trends_data, market)
            logger.info(f"✅ Stock: {len(trends_data)}件のデータを取得し、キャッシュに保存しました (market: {market})")
            
            # レスポンス時はlimitで制限
            return_data = trends_data[:limit]
            
            return {
                'success': True,
                'data': return_data,
                'status': 'api_fetched',
                'source': 'yfinance',
                'market': market,
                'total_count': len(trends_data)  # 全件数を返す
            }
            
        except Exception as e:
            logger.error(f"❌ Stock API エラー: {e}", exc_info=True)
            return {
                'error': f'株価データ取得エラー: {str(e)}',
                'success': False
            }

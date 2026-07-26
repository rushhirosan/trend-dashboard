"""
GlobeNewswire × Market Reaction トレンドマネージャー
GlobeNewswire RSS からプレスリリースを取得し、ティッカーを抽出。
yfinance で株価・出来高を取得し、abs(24h%change) + volume_spike でスコアを算出。
反応ランキング Top N を返す。
"""

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import feedparser
import pandas as pd
import requests
import yfinance as yf

from database_config import TrendsCache
from services.trends.base_trends_manager import BaseTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)


def _safe_float(val, default: float = 0.0) -> float:
    """yfinance / DB 由来の NaN・Decimal・文字列を安全な float に落とす。"""
    try:
        if val is None:
            return default
        if isinstance(val, Decimal):
            if not val.is_finite():
                return default
            return float(val)
        if isinstance(val, bool):
            return default
        if isinstance(val, (int, float)):
            f = float(val)
            return f if math.isfinite(f) else default
        if isinstance(val, str):
            cleaned = val.strip().replace("%", "").replace(",", "")
            if cleaned == "":
                return default
            f = float(cleaned)
            return f if math.isfinite(f) else default
        f = float(val)
        return f if math.isfinite(f) else default
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return default

# GlobeNewswire 公式ATOM（Public Companies）
DEFAULT_RSS_URL = (
    "https://www.globenewswire.com/AtomFeed/orgclass/1/"
    "feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies"
)

# ティッカー抽出用正規表現: (NASDAQ:AAPL), (NYSE:MSFT), (AMEX:XXX), (TSX:XXX) など
TICKER_PATTERN = re.compile(
    r'\(?(?:NASDAQ|NYSE|AMEX|TSX|OTC)[:\s]+([A-Z0-9\.\-]+)\)?',
    re.IGNORECASE
)

TOP_N = 15


class GlobeNewswireMarketReactionTrendsManager(BaseTrendsManager):
    """GlobeNewswire × Market Reaction（株価/出来高）で反応ランキング"""

    def __init__(self):
        super().__init__(service_name='globenewswire_market_reaction', max_requests=15, window_seconds=60)
        self.rss_url = DEFAULT_RSS_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrendDashboard/1.0 (trend detection; link-out only)',
            'Accept': 'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        logger.info("GlobeNewswire × Market Reaction Trends Manager 初期化")

    def _get_cache_key(self, *args, **kwargs):
        return 'globenewswire_market_reaction_trends'

    def _get_from_cache(self, *args, **kwargs):
        try:
            return self.db.get_globenewswire_market_reaction_trends_from_cache() or []
        except Exception as e:
            logger.error(f"❌ GlobeNewswire×Market: キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data, *args, **kwargs):
        try:
            return self.db.save_globenewswire_market_reaction_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ GlobeNewswire×Market キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        try:
            return self.db.clear_globenewswire_market_reaction_trends_cache()
        except Exception as e:
            logger.error(f"❌ GlobeNewswire×Market キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ GlobeNewswire×Market: cache_status更新エラー: {e}")
            return False

    def _extract_ticker(self, item: dict) -> str | None:
        """タイトル・タグ・description からティッカーを抽出"""
        text_parts = []
        if item.get('title'):
            text_parts.append(item['title'])
        if item.get('description'):
            text_parts.append(item['description'])
        for t in (item.get('tags') or []):
            term = t.get('term') if isinstance(t, dict) else getattr(t, 'term', None)
            if term:
                text_parts.append(str(term))

        combined = ' '.join(text_parts)
        match = TICKER_PATTERN.search(combined)
        if match:
            ticker = match.group(1).strip().upper()
            if len(ticker) >= 1 and len(ticker) <= 10:
                return ticker
        return None

    def _parse_feed(self) -> list[dict]:
        """RSS を取得してエントリ一覧を返す"""
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(self.rss_url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"GlobeNewswire RSS status: {resp.status_code}")
                return []
            parsed = feedparser.parse(resp.content)
            items = []
            for e in parsed.entries:
                link = e.get('link') or (e.get('links') or [{}])[0].get('href') or ''
                title = (e.get('title') or '').strip()
                if not link or not title:
                    continue
                published = None
                for key in ('published', 'updated', 'created'):
                    val = e.get(key)
                    if val:
                        try:
                            if hasattr(val, 'timestamp'):
                                published = datetime.utcfromtimestamp(val.timestamp()).isoformat() + 'Z'
                            else:
                                published = val
                            break
                        except Exception:
                            published = val
                            break
                description = (e.get('summary') or e.get('description') or '')
                if hasattr(description, 'strip'):
                    description = description.strip()[:500] if description else ''
                tags = []
                for t in (getattr(e, 'tags', None) or []):
                    if isinstance(t, dict):
                        tags.append({'term': t.get('term'), 'scheme': t.get('scheme'), 'label': t.get('label')})
                    else:
                        tags.append({
                            'term': getattr(t, 'term', None),
                            'scheme': getattr(t, 'scheme', None),
                            'label': getattr(t, 'label', None),
                        })
                items.append({
                    'title': title,
                    'url': link,
                    'published_date': published or '',
                    'description': description or '',
                    'tags': tags,
                })
            return items
        except Exception as e:
            logger.warning(f"GlobeNewswire RSS取得エラー: {e}")
            return []

    def _fetch_market_data_batch(self, tickers: list[str]) -> dict[str, dict]:
        """
        yfinance で複数ティッカーの 24h%change と volume_spike を取得。
        返り値: {ticker: {change_percent: float, volume_spike: float}}
        yf.download で一括取得を試み、失敗時は個別取得にフォールバック。
        """
        if not tickers:
            return {}

        result = {t: {'change_percent': 0, 'volume_spike': 0} for t in tickers}

        def _calc_from_hist(hist: pd.DataFrame) -> tuple[float, float]:
            """hist DataFrame から change_pct と vol_spike を計算（NaN は 0）。"""
            if hist is None or hist.empty or len(hist) < 2:
                return 0.0, 0.0
            close = hist['Close'] if 'Close' in hist.columns else None
            vol = hist['Volume'] if 'Volume' in hist.columns else pd.Series([0] * len(hist))
            if close is None or close.empty:
                return 0.0, 0.0
            prev_close = _safe_float(close.iloc[-2])
            curr_close = _safe_float(close.iloc[-1])
            change_pct = (curr_close / prev_close - 1) * 100 if prev_close > 0 else 0.0
            curr_vol = _safe_float(vol.iloc[-1]) if len(vol) > 0 else 0.0
            if len(vol) > 1:
                avg_vol = _safe_float(vol.iloc[:-1].mean(), curr_vol)
            else:
                avg_vol = curr_vol
            if avg_vol > 0:
                vol_spike = min(50.0, max(0.0, (curr_vol / avg_vol - 1) * 100))
            else:
                vol_spike = 0.0
            return _safe_float(change_pct), _safe_float(vol_spike)

        try:
            # yf.download で一括取得（1リクエスト）
            df = yf.download(
                tickers,
                period='5d',
                interval='1d',
                group_by='ticker',
                auto_adjust=True,
                progress=False,
                threads=False,
                timeout=20,
                session=self.session,
            )

            if df.empty:
                return result

            # 単一ティッカーの場合: カラムはフラット
            if len(tickers) == 1:
                ticker = tickers[0]
                change_pct, vol_spike = _calc_from_hist(df)
                result[ticker] = {'change_percent': change_pct, 'volume_spike': vol_spike}
                return result

            # 複数ティッカー: MultiIndex カラム (Ticker, OHLCV)
            if isinstance(df.columns, pd.MultiIndex):
                for ticker in tickers:
                    try:
                        if ticker in df.columns.get_level_values(0):
                            ticker_df = df[ticker].copy()
                            change_pct, vol_spike = _calc_from_hist(ticker_df)
                            result[ticker] = {'change_percent': change_pct, 'volume_spike': vol_spike}
                    except Exception as e:
                        logger.debug(f"ティッカー {ticker} パースエラー: {e}")
            else:
                # フォールバック: 個別取得
                for ticker in tickers:
                    try:
                        self.rate_limiter.wait_if_needed()
                        t = yf.Ticker(ticker, session=self.session)
                        hist = t.history(period='5d', timeout=10)
                        change_pct, vol_spike = _calc_from_hist(hist)
                        result[ticker] = {'change_percent': change_pct, 'volume_spike': vol_spike}
                    except Exception as e:
                        logger.debug(f"ティッカー {ticker} 取得エラー: {e}")

        except Exception as e:
            logger.warning(f"yfinance 一括取得エラー、個別取得にフォールバック: {e}")
            for ticker in tickers:
                try:
                    self.rate_limiter.wait_if_needed()
                    t = yf.Ticker(ticker, session=self.session)
                    hist = t.history(period='5d', timeout=10)
                    change_pct, vol_spike = _calc_from_hist(hist)
                    result[ticker] = {'change_percent': change_pct, 'volume_spike': vol_spike}
                except Exception as ex:
                    logger.debug(f"ティッカー {ticker} 取得エラー: {ex}")

        return result

    def get_trends(self, limit=TOP_N, force_refresh=False):
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key='reaction_score',
            sort_reverse=True,
        )

    def _fetch_trends(self, limit=TOP_N, *args, **kwargs):
        """
        GlobeNewswire RSS → ティッカー抽出 → 株価・出来高取得 → スコア算出 → Top N
        スコア = abs(24h%change) + volume_spike
        """
        try:
            logger.info("GlobeNewswire × Market Reaction: 取得開始")
            items = self._parse_feed()
            if not items:
                logger.warning("GlobeNewswire × Market Reaction: RSS 0件")
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'globenewswire_market_reaction',
                    'total_count': 0,
                }

            # ティッカー抽出（重複除去）
            ticker_to_items: dict[str, list[dict]] = {}
            for item in items:
                ticker = self._extract_ticker(item)
                if ticker:
                    if ticker not in ticker_to_items:
                        ticker_to_items[ticker] = []
                    ticker_to_items[ticker].append(item)

            unique_tickers = list(ticker_to_items.keys())
            if not unique_tickers:
                logger.warning("GlobeNewswire × Market Reaction: ティッカー抽出 0件")
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'globenewswire_market_reaction',
                    'total_count': 0,
                }

            logger.info(f"GlobeNewswire × Market Reaction: {len(unique_tickers)} ティッカー抽出")

            self.rate_limiter.wait_if_needed()
            market_data = self._fetch_market_data_batch(unique_tickers)

            # スコア算出とマージ（各ティッカーで最新1件のみ使用）
            # NaN / Decimal は float 化して 0 に落とす（ソート・round で InvalidOperation を防ぐ）
            scored_items = []
            for ticker, item_list in ticker_to_items.items():
                item = item_list[0]
                md = market_data.get(ticker, {'change_percent': 0, 'volume_spike': 0})
                change_pct = _safe_float(md.get('change_percent', 0))
                vol_spike = _safe_float(md.get('volume_spike', 0))
                score = abs(change_pct) + vol_spike

                item['ticker'] = ticker
                item['change_percent'] = round(change_pct, 2)
                item['volume_spike'] = round(vol_spike, 2)
                item['reaction_score'] = round(score, 2)
                scored_items.append(item)

            scored_items.sort(key=lambda x: _safe_float(x.get('reaction_score', 0)), reverse=True)
            top = scored_items[:limit]
            for i, item in enumerate(top, 1):
                item['rank'] = i

            logger.info(f"✅ GlobeNewswire × Market Reaction: {len(top)}件（スコア順）")
            return {
                'success': True,
                'data': top,
                'status': 'api_fetched',
                'source': 'globenewswire_market_reaction',
                'total_count': len(top),
            }

        except requests.exceptions.Timeout:
            logger.error("❌ GlobeNewswire × Market Reaction タイムアウト", exc_info=True)
            return {'success': False, 'error': 'タイムアウトしました', 'data': []}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ GlobeNewswire × Market Reaction リクエストエラー: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}
        except Exception as e:
            logger.error(f"❌ GlobeNewswire × Market Reaction 取得エラー: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}

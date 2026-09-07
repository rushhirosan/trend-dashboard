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

# タイトル等向け: (NASDAQ:AAPL) / NYSE:MSFT など（後方互換）
TICKER_PATTERN = re.compile(
    r'\(?(?:NASDAQ(?:CM|GM|GS)?|NYSE(?:\s+AMERICAN)?|AMEX|TSX(?:-?V)?|OTC|PARIS|LSE|LONDON)'
    r'[:\s]+([A-Z0-9\.\-]+)\)?',
    re.IGNORECASE,
)

# category term "Paris:ALD" / "NYSE:DLR"（stock scheme）向け
STOCK_TAG_PATTERN = re.compile(
    r'^([A-Za-z][A-Za-z0-9 \-]{0,24}):([A-Z0-9][A-Z0-9\.\-]{0,9})$'
)

# GlobeNewswire の取引所名 → Yahoo Finance サフィックス（空文字=米国など無印）
# Public Companies フィードは欧州寄りになることがあり、US限定だと 0 件になる
EXCHANGE_YAHOO_SUFFIX: dict[str, str] = {
    'NASDAQ': '',
    'NASDAQCM': '',
    'NASDAQGM': '',
    'NASDAQGS': '',
    'NYSE': '',
    'NYSE AMERICAN': '',
    'AMEX': '',
    'OTC': '',
    'OTCQB': '',
    'OTCQX': '',
    'TSX': 'TO',
    'TSXV': 'V',
    'TSX-V': 'V',
    'CSE': 'CN',
    'PARIS': 'PA',
    'LSE': 'L',
    'LONDON': 'L',
    'STOCKHOLM': 'ST',
    'OSLO': 'OL',
    'AMSTERDAM': 'AS',
    'BRUSSELS': 'BR',
    'HELSINKI': 'HE',
    'COPENHAGEN': 'CO',
    'FRANKFURT': 'F',
    'XETRA': 'DE',
    'SWISS': 'SW',
    'SIX': 'SW',
    'ASX': 'AX',
    'HKEX': 'HK',
    'HONG KONG': 'HK',
    'TOKYO': 'T',
}

TOP_N = 15
# GlobeNewswire は間欠的に遅いことがあるため、15秒ではタイムアウトしやすい
RSS_TIMEOUT_SECONDS = 30
# 初回失敗後に 1 回だけリトライ（合計 2 試行）
RSS_MAX_ATTEMPTS = 2


def _normalize_exchange(name: str) -> str:
    return re.sub(r'\s+', ' ', (name or '').strip().upper())


def _to_yahoo_symbol(exchange: str, symbol: str) -> str | None:
    """取引所名 + 銘柄コードを yfinance 用シンボルに変換。未対応取引所は None。"""
    exch = _normalize_exchange(exchange)
    sym = (symbol or '').strip().upper()
    if not sym or len(sym) > 10:
        return None
    if exch not in EXCHANGE_YAHOO_SUFFIX:
        return None
    suffix = EXCHANGE_YAHOO_SUFFIX[exch]
    return f'{sym}.{suffix}' if suffix else sym


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
        """
        タイトル・タグ・description から yfinance 用ティッカーを抽出。
        優先: stock scheme の category（例: Paris:ALD / NYSE:DLR）
        """
        # 1) RSS stock category（最も信頼できる）
        for t in (item.get('tags') or []):
            if isinstance(t, dict):
                term = t.get('term')
                scheme = (t.get('scheme') or '') or ''
                label = t.get('label')
            else:
                term = getattr(t, 'term', None)
                scheme = getattr(t, 'scheme', None) or ''
                label = getattr(t, 'label', None)

            prefer_stock_scheme = 'rss/stock' in str(scheme).lower()
            for raw in (term, label):
                if not raw:
                    continue
                m = STOCK_TAG_PATTERN.match(str(raw).strip())
                if not m:
                    continue
                yahoo = _to_yahoo_symbol(m.group(1), m.group(2))
                if yahoo:
                    return yahoo
                # stock scheme で未対応取引所なら次へ（誤抽出を避ける）
                if prefer_stock_scheme:
                    continue

        # 2) タイトル / description / 全タグ文字列（従来形式）
        text_parts = []
        if item.get('title'):
            text_parts.append(item['title'])
        if item.get('description'):
            text_parts.append(item['description'])
        for t in (item.get('tags') or []):
            term = t.get('term') if isinstance(t, dict) else getattr(t, 'term', None)
            label = t.get('label') if isinstance(t, dict) else getattr(t, 'label', None)
            if term:
                text_parts.append(str(term))
            if label:
                text_parts.append(str(label))

        combined = ' '.join(text_parts)
        match = TICKER_PATTERN.search(combined)
        if not match:
            return None
        symbol = match.group(1).strip().upper()
        around = combined[max(0, match.start() - 24):match.end()]
        exch_match = re.search(
            r'(NASDAQ(?:CM|GM|GS)?|NYSE(?:\s+AMERICAN)?|AMEX|TSX(?:-?V)?|OTC(?:QB|QX)?'
            r'|PARIS|LSE|LONDON|STOCKHOLM|OSLO|AMSTERDAM|BRUSSELS|HELSINKI|'
            r'COPENHAGEN|FRANKFURT|XETRA|SWISS|SIX|ASX|HKEX|HONG\s+KONG|TOKYO|CSE)',
            around,
            re.IGNORECASE,
        )
        if exch_match:
            return _to_yahoo_symbol(exch_match.group(1), symbol)
        if 1 <= len(symbol) <= 10:
            return symbol
        return None

    def _entries_from_parsed(self, parsed) -> list[dict]:
        """feedparser 結果からエントリ一覧を組み立てる"""
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

    def _parse_feed(self) -> tuple[list[dict], str | None]:
        """
        RSS を取得してエントリ一覧を返す。
        返り値: (items, empty_reason)。items があるときは empty_reason は None。
        """
        last_reason: str | None = None
        for attempt in range(1, RSS_MAX_ATTEMPTS + 1):
            try:
                self.rate_limiter.wait_if_needed()
                resp = self.session.get(self.rss_url, timeout=RSS_TIMEOUT_SECONDS)
                if resp.status_code != 200:
                    last_reason = (
                        f"RSS取得失敗（HTTP {resp.status_code}）。"
                        "一時的な不調の可能性があります。"
                    )
                    logger.warning(
                        "GlobeNewswire RSS status: %s (attempt %s/%s)",
                        resp.status_code,
                        attempt,
                        RSS_MAX_ATTEMPTS,
                    )
                    if attempt < RSS_MAX_ATTEMPTS:
                        continue
                    return [], last_reason

                parsed = feedparser.parse(resp.content)
                items = self._entries_from_parsed(parsed)
                if not items:
                    return [], "RSSフィードは取得できましたがエントリが0件でした。"
                if attempt > 1:
                    logger.info(
                        "GlobeNewswire RSS: リトライ成功（attempt %s/%s, %s件）",
                        attempt,
                        RSS_MAX_ATTEMPTS,
                        len(items),
                    )
                return items, None

            except requests.exceptions.Timeout:
                last_reason = (
                    f"RSS取得がタイムアウトしました"
                    f"（{RSS_TIMEOUT_SECONDS}秒×{RSS_MAX_ATTEMPTS}回）。"
                    "一時的な遅延の可能性があります。"
                )
                logger.warning(
                    "GlobeNewswire RSS タイムアウト (attempt %s/%s)",
                    attempt,
                    RSS_MAX_ATTEMPTS,
                )
                if attempt < RSS_MAX_ATTEMPTS:
                    continue
                return [], last_reason
            except requests.exceptions.RequestException as e:
                last_reason = f"RSS取得リクエストエラー: {e}"
                logger.warning(
                    "GlobeNewswire RSS リクエストエラー (attempt %s/%s): %s",
                    attempt,
                    RSS_MAX_ATTEMPTS,
                    e,
                )
                if attempt < RSS_MAX_ATTEMPTS:
                    continue
                return [], last_reason
            except Exception as e:
                last_reason = f"RSS解析エラー: {e}"
                logger.warning(f"GlobeNewswire RSS取得エラー: {e}")
                return [], last_reason

        return [], last_reason or "RSS取得に失敗しました。"

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
            items, rss_empty_reason = self._parse_feed()
            if not items:
                reason = rss_empty_reason or "RSS 0件（原因不明）"
                logger.warning("GlobeNewswire × Market Reaction: %s", reason)
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'globenewswire_market_reaction',
                    'total_count': 0,
                    'empty_reason': reason,
                    'message': reason,
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
                seen_exchanges: list[str] = []
                for item in items:
                    for t in (item.get('tags') or []):
                        term = t.get('term') if isinstance(t, dict) else getattr(t, 'term', None)
                        if not term:
                            continue
                        m = STOCK_TAG_PATTERN.match(str(term).strip())
                        if m:
                            exch = _normalize_exchange(m.group(1))
                            if exch not in seen_exchanges:
                                seen_exchanges.append(exch)
                if seen_exchanges:
                    reason = (
                        f"RSSエントリは{len(items)}件ありましたが、"
                        f"対応マーケットへ変換できるティッカーがありませんでした"
                        f"（検出: {', '.join(seen_exchanges[:8])}）。"
                    )
                else:
                    reason = (
                        f"RSSエントリは{len(items)}件ありましたが、"
                        "ティッカー（NYSE/NASDAQ/Paris/LSE 等）を抽出できませんでした。"
                    )
                logger.warning("GlobeNewswire × Market Reaction: %s", reason)
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'globenewswire_market_reaction',
                    'total_count': 0,
                    'empty_reason': reason,
                    'message': reason,
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

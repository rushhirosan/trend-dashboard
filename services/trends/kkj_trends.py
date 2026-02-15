"""
官公需情報ポータルサイト検索API で Public Sector Signals（直近30日×AI/DX/サイバー件数）
および都道府県ランキング（DX案件 Top5）を取得するマネージャー。
APIキー不要。http://www.kkj.go.jp/api/
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlencode

from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

KKJ_API_BASE = "http://www.kkj.go.jp/api/"

# 直近何日分を対象にするか
SIGNALS_DAYS = 30

# Public Sector Signals 用キーワード（APIのQueryパラメータ）
SIGNALS_QUERIES = [
    ("ai", "AI関連", "AI OR 人工知能"),
    ("dx", "DX関連", "DX OR デジタル"),
    ("cyber", "サイバー", "サイバー"),
]

# 都道府県ランキング用: 単一キーワードで取得（APIが "OR" 付きでは結果リストを返さない場合があるため）
RANKING_QUERIES = [
    ("ai", "AI関連", "人工知能"),
    ("dx", "DX関連", "デジタル"),
    ("cyber", "サイバー", "サイバー"),
]
RANKING_COUNT = 1000

# JIS X 0401 都道府県コード → 都道府県名（APIの LG_Code 用）
LG_CODE_TO_PREFECTURE = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県", "05": "秋田県",
    "06": "山形県", "07": "福島県", "08": "茨城県", "09": "栃木県", "10": "群馬県",
    "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "15": "新潟県",
    "16": "富山県", "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県", "25": "滋賀県",
    "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県",
    "36": "徳島県", "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県", "45": "宮崎県",
    "46": "鹿児島県", "47": "沖縄県",
}


def _text(elem: Optional[ET.Element]) -> str:
    if elem is None or elem.text is None:
        return ""
    return (elem.text or "").strip()


def _parse_date_range(days: int) -> str:
    """APIの期間形式 'YYYY-MM-DD' を返す（その日以降）。e-Govではハイフン区切りが標準。"""
    start = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime("%Y-%m-%d")


def _strip_namespace(element: ET.Element) -> None:
    """要素と子孫のタグから名前空間を除去（{ns}Tag → Tag）"""
    if element.tag.startswith("{"):
        element.tag = element.tag.split("}", 1)[1]
    for child in element:
        _strip_namespace(child)


def _fetch_kkj_xml(params: Dict[str, str], timeout: int = 45) -> Optional[ET.Element]:
    """官公需APIにGETで問い合わせ、XMLのルート要素を返す。エラー時はNone。"""
    url = KKJ_API_BASE + "?" + urlencode(params)
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        raw = r.content
        root = ET.fromstring(raw)
        _strip_namespace(root)  # 名前空間を除去してタグ名で検索しやすくする
        return root
    except requests.RequestException as e:
        logger.warning("官公需API リクエストエラー（タイムアウトや接続不可の可能性）: %s", e)
        return None
    except ET.ParseError as e:
        logger.warning("官公需API XMLパースエラー: %s", e)
        return None


def _find_element(root: ET.Element, *tags: str) -> Optional[ET.Element]:
    """複数のタグ名を試して最初に見つかった要素を返す（大文字小文字の違いに対応）"""
    for tag in tags:
        el = root.find(tag)
        if el is not None:
            return el
    return None


def _find_all(root: ET.Element, *parent_tags: str) -> List[ET.Element]:
    """SearchResult 要素のリストを返す。"""
    parent = _find_element(root, *parent_tags)
    if parent is not None:
        for child_tag in ("SearchResult", "searchresult"):
            items = parent.findall(child_tag)
            if items:
                return items
    # 親が見つからない場合は root 直下を探す
    for tag in ("SearchResult", "searchresult"):
        items = root.findall(tag)
        if items:
            return items
    return []


def _iter_all_elements(element: ET.Element):
    """要素とその子孫を再帰的に yield。"""
    yield element
    for child in element:
        yield from _iter_all_elements(child)


def _get_search_hits(root: ET.Element) -> Optional[int]:
    """SearchHits または SearchResults 内の件数を返す。APIは PascalCase を使用。"""
    # ルート直下の SearchHits を試す
    for hits_tag in ("SearchHits", "searchhits"):
        hits = root.find(hits_tag)
        if hits is not None and hits.text:
            try:
                return int((hits.text or "").strip())
            except ValueError:
                pass
    # SearchResults 内の SearchHits を試す
    for parent_tag in ("SearchResults", "searchresults", "Results", "results"):
        parent = root.find(parent_tag)
        if parent is None:
            continue
        for hits_tag in ("SearchHits", "searchhits"):
            hits = parent.find(hits_tag)
            if hits is not None and hits.text:
                try:
                    return int((hits.text or "").strip())
                except ValueError:
                    pass
    # 子孫をたどって SearchHits を探す（名前空間付きやネストが深い場合）
    for el in _iter_all_elements(root):
        if el.tag and el.tag.lower().endswith("searchhits") and el.text:
            try:
                return int((el.text or "").strip())
            except ValueError:
                pass
    # SearchHits が無い場合は SearchResult の件数で代用
    items = _find_all(root, "SearchResults", "searchresults")
    if items:
        return len(items)
    return None


def _get_error_message(root: ET.Element) -> Optional[str]:
    """<error> または <Error> があればメッセージを返す。"""
    for tag in ("error", "Error"):
        err = root.find(tag)
        if err is not None and err.text:
            return (err.text or "").strip()
    return None


def _lg_code_to_prefecture(code: str) -> str:
    """都道府県コード（2桁または5桁）を都道府県名に変換。"""
    if not code:
        return ""
    s = (code or "").strip()
    if len(s) >= 2:
        two = s[:2]
        return LG_CODE_TO_PREFECTURE.get(two, "")
    return ""


def _get_prefecture_from_result(sr: ET.Element) -> str:
    """SearchResult 要素から都道府県名を抽出。APIは Organization_Name, LG_Code 等を使用。"""
    # 1. PrefectureName, Organization_Name など都道府県名らしき文字列
    for tag in ("PrefectureName", "prefecturename", "Organization_Name", "OrganizationName"):
        el = sr.find(tag)
        if el is not None and el.text:
            text = (el.text or "").strip()
            if text:
                return text
    # 2. LG_Code（都道府県コード）があれば都道府県名に変換（AI/サイバー等でこちらだけ返る場合あり）
    for tag in ("LG_Code", "lg_code", "LGCode"):
        el = sr.find(tag)
        if el is not None and el.text:
            name = _lg_code_to_prefecture(el.text)
            if name:
                return name
    return ""


def _fetch_hits_for_query(
    query: str, date_from: str, count: int = 1, rate_limiter=None
) -> Tuple[Optional[int], List[Dict[str, Any]], bool]:
    """
    1回の検索で SearchHits（総件数）と結果リストを返す。
    Returns: (search_hits or None, list_of_result_dicts, connection_ok).
    connection_ok が False のときはタイムアウト等でAPIに接続できなかった。
    """
    if rate_limiter:
        rate_limiter.wait_if_needed()
    params = {
        "Query": query,
        "CFT_Issue_Date": date_from,
        "Count": str(count),
    }
    root = _fetch_kkj_xml(params)
    if root is None:
        return 0, [], False  # 接続失敗
    err = _get_error_message(root)
    if err:
        logger.warning("官公需API エラー: %s", err)
        return 0, [], True
    hits = _get_search_hits(root)
    total = hits if hits is not None else 0
    if total == 0 and root is not None:
        child_tags = [c.tag for c in root if c.tag]
        logger.info("官公需API 0件: Query=%s, CFT_Issue_Date=%s, root.tag=%s, 子=%s", query[:30], date_from, root.tag, child_tags[:15])
    results = []
    for sr in _find_all(root, "SearchResults", "searchresults"):
        pref = _get_prefecture_from_result(sr)
        if pref and ("県" in pref or "府" in pref or "都" in pref):
            pass
        elif pref:
            m = re.search(r"^(北海道|東京都|大阪府|京都府|.{2,4}県)", pref)
            pref = m.group(1) if m else pref
        results.append({"prefecture": pref})
    return total, results, True


class KKJTrendsManager(BaseTrendsManager):
    """官公需API で Public Sector Signals と都道府県ランキングを取得するマネージャー"""

    def __init__(self):
        super().__init__(service_name="kkj", max_requests=10, window_seconds=60)

    def _get_cache_key(self, *args, **kwargs) -> str:
        return "kkj_trends"

    def _get_from_cache(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        try:
            return self.db.get_kkj_trends_from_cache()
        except Exception as e:
            logger.debug("kkj キャッシュ取得: %s", e)
            return None

    def _save_to_cache(self, data: Any, *args, **kwargs) -> bool:
        try:
            # data は { signals, prefecture_ranking, ... } の辞書
            return self.db.save_kkj_trends_to_cache(data)
        except Exception as e:
            logger.warning("kkj キャッシュ保存スキップ: %s", e)
            return False

    def _clear_cache(self, *args, **kwargs) -> bool:
        try:
            return self.db.clear_kkj_trends_cache()
        except Exception as e:
            logger.debug("kkj キャッシュクリア: %s", e)
            return False

    def _fetch_trends(self, *args, **kwargs) -> Dict[str, Any]:
        date_from = _parse_date_range(SIGNALS_DAYS)
        as_of = datetime.now().strftime("%Y-%m-%d %H:%M")

        # --- Public Sector Signals: キーワード別件数 ---
        signals = []
        connection_ok_count = 0
        for key, label, query in SIGNALS_QUERIES:
            total, _, ok = _fetch_hits_for_query(
                query, date_from, count=1, rate_limiter=self.rate_limiter
            )
            if ok:
                connection_ok_count += 1
            signals.append({
                "key": key,
                "label": label,
                "count": total if total is not None else 0,
                "trend": "up",
            })

        # --- 都道府県ランキング: AI / DX / サイバーそれぞれで取得して Top5 ---
        prefecture_rankings: Dict[str, List[Dict[str, Any]]] = {}
        for key, label, query in RANKING_QUERIES:
            _, results, ok = _fetch_hits_for_query(
                query, date_from, count=RANKING_COUNT, rate_limiter=self.rate_limiter
            )
            if ok:
                connection_ok_count += 1
            prefecture_counts = {}
            for r in results:
                pref = (r.get("prefecture") or "").strip()
                if not pref:
                    continue
                prefecture_counts[pref] = prefecture_counts.get(pref, 0) + 1
            prefecture_rankings[key] = [
                {"rank": i, "name": name, "count": cnt}
                for i, (name, cnt) in enumerate(
                    sorted(prefecture_counts.items(), key=lambda x: -x[1])[:5], start=1
                )
            ]
        # 後方互換: prefecture_ranking は DX のランキング
        ranking = prefecture_rankings.get("dx", [])

        # 6回中1回も接続できなかった場合は「APIに接続できません」と分かるようにする
        api_unreachable = connection_ok_count == 0
        payload = {
            "signals": signals,
            "prefecture_ranking": ranking,
            "prefecture_rankings": prefecture_rankings,
            "period_days": SIGNALS_DAYS,
            "as_of": as_of,
            "api_unreachable": api_unreachable,
        }
        return {
            "success": True,
            "data": payload,
            "status": "api_fetched",
            "source": "官公需情報ポータルサイト検索API",
        }

    def _has_any_signal_count(self, data: Dict[str, Any]) -> bool:
        """payload に1件でも count > 0 の signal があれば True。"""
        signals = data.get("signals") or []
        return any((s.get("count") or 0) > 0 for s in signals)

    def get_public_sector_signals(
        self, force_refresh: bool = False, cache_only: bool = False
    ) -> Dict[str, Any]:
        """
        Public Sector Signals と都道府県ランキングを返す。
        有効なキャッシュがあればそれを返す。cache_only=True のときは外部APIを呼ばず
        キャッシュのみ返す（無い場合は空で返す）。再取得は force_refresh=True のときのみ。
        """
        cached = None if force_refresh else self._get_from_cache()
        if cached is not None and self._has_any_signal_count(cached):
            return {
                "success": True,
                "data": cached,
                "status": "cached",
                "source": "官公需情報ポータルサイト検索API",
            }
        if cache_only:
            return {
                "success": True,
                "data": {"signals": [], "prefecture_ranking": [], "prefecture_rankings": {}, "period_days": 30, "as_of": ""},
                "status": "cache_only_empty",
                "source": "官公需情報ポータルサイト検索API",
            }
        result = self._fetch_trends()
        data = result.get("data") if result.get("success") else None
        if data:
            if self._has_any_signal_count(data):
                self._save_to_cache(data)
            else:
                # APIが0件を返した場合はキャッシュを上書きしない。
                fallback = self._get_from_cache()
                if fallback is not None and self._has_any_signal_count(fallback):
                    return {
                        "success": True,
                        "data": fallback,
                        "status": "cached",
                        "source": "官公需情報ポータルサイト検索API",
                    }
                # キャッシュも0件の場合は悪いキャッシュをクリアし、次回の再取得でまっさらから試せるようにする
                if fallback is not None:
                    self._clear_cache()
        return result

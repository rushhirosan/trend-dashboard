"""
官公需情報ポータルサイト検索API で Public Sector Signals（直近30日×AI/DX/サイバー件数）
および都道府県ランキング（DX案件 Top5）を取得するマネージャー。
APIキー不要。http://www.kkj.go.jp/api/
"""

import calendar
import gc
import os
import re
import time
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
# キーワード別月次データの取得月数（直近）
SIGNALS_MONTHS = 12

# カテゴリ定義（表示用ラベル）。キーワードをカテゴリ化して表示する
KKJ_CATEGORY_LABELS = {
    "digital": "デジタル技術",
    "security": "セキュリティ",
}
# 表示順
KKJ_CATEGORY_ORDER = ["digital", "security"]

# Public Sector Signals 用キーワード（key, 表示ラベル, APIのQuery, カテゴリkey）
SIGNALS_QUERIES = [
    ("ai", "AI関連", "AI OR 人工知能", "digital"),
    ("dx", "DX関連", "DX OR デジタル", "digital"),
    ("cyber", "サイバー", "サイバー", "security"),
]

# 都道府県ランキング用: 単一キーワードで取得（APIが "OR" 付きでは結果リストを返さない場合があるため）
RANKING_QUERIES = [
    ("ai", "AI関連", "人工知能", "digital"),
    ("dx", "DX関連", "デジタル", "digital"),
    ("cyber", "サイバー", "サイバー", "security"),
]
RANKING_COUNT = 1000
# 低メモリ refresh subprocess 用（県別 Top5 集計には十分な上限）
LOW_MEMORY_RANKING_COUNT = 150


def _ranking_fetch_count() -> int:
    raw = os.environ.get("KKJ_RANKING_FETCH_COUNT")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(25, min(RANKING_COUNT, int(raw)))
        except (TypeError, ValueError):
            pass
    return RANKING_COUNT


# JP chunk subprocess 上限（既定 600s）より短く打ち切り、kill 前に stale cache を返す。
_KKJ_FETCH_DEADLINE_DEFAULT = 480.0
_KKJ_FETCH_DEADLINE_MAX = 570.0


class KkjFetchDeadlineExceeded(Exception):
    """官公需APIの連続取得が全体期限を超えた。"""


def _kkj_fetch_deadline_seconds() -> float:
    raw = os.environ.get("KKJ_FETCH_DEADLINE_SECONDS")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(60.0, min(_KKJ_FETCH_DEADLINE_MAX, float(raw)))
        except (TypeError, ValueError):
            pass
    return _KKJ_FETCH_DEADLINE_DEFAULT


def _ensure_kkj_deadline(deadline_at: Optional[float]) -> None:
    if deadline_at is not None and time.monotonic() >= deadline_at:
        raise KkjFetchDeadlineExceeded("kkj_fetch_deadline")

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
    """APIの期間形式 'YYYY-MM-DD/' を返す（その日以降）。APIガイド: 開始日/ で終了日なし＝以降。"""
    start = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime("%Y-%m-%d") + "/"


def _month_range(year: int, month: int) -> Tuple[str, str]:
    """指定年月の月初日・月末日を API 形式 'YYYY-MM-DD' で返す。"""
    first = f"{year:04d}-{month:02d}-01"
    _, last_day = calendar.monthrange(year, month)
    last = f"{year:04d}-{month:02d}-{last_day:02d}"
    return first, last


def _last_n_months(n: int) -> List[Tuple[int, int]]:
    """直近 n ヶ月の (year, month) のリストを新しい順で返す。"""
    now = datetime.now()
    y, m = now.year, now.month
    out: List[Tuple[int, int]] = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m <= 0:
            m += 12
            y -= 1
    return out


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
    """SearchResult 要素のリストを返す。APIはルートが SearchResults のことがある。"""
    # ルート自身が SearchResults の場合はその子が SearchResult
    root_tag = (root.tag or "").strip()
    if root_tag and root_tag.lower().replace("_", "") == "searchresults":
        for child_tag in ("SearchResult", "searchresult"):
            items = root.findall(child_tag)
            if items:
                return items
    # 子要素に SearchResults がある場合
    parent = _find_element(root, *parent_tags)
    if parent is not None:
        for child_tag in ("SearchResult", "searchresult"):
            items = parent.findall(child_tag)
            if items:
                return items
    # root 直下の SearchResult
    for tag in ("SearchResult", "searchresult"):
        items = root.findall(tag)
        if items:
            return items
    # 子孫をたどって SearchResult をすべて収集（ネストや名前空間の違いに対応）
    out: List[ET.Element] = []
    for el in root.iter():
        if el.tag and el.tag.lower().replace("_", "") == "searchresult":
            out.append(el)
    return out


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


def _get_child_text(element: ET.Element, *tags: str) -> str:
    """子要素のテキストを返す。複数タグ名を試す（大文字小文字の違いに対応）。"""
    for tag in tags:
        el = element.find(tag)
        if el is not None:
            text = (el.text or "").strip()
            if text:
                return text
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


def _get_case_from_result(sr: ET.Element) -> Dict[str, Any]:
    """SearchResult 要素から案件情報（件名・URL・機関・公告日・都道府県）を抽出。"""
    pref = _get_prefecture_from_result(sr)
    if pref and ("県" not in pref and "府" not in pref and "都" not in pref):
        m = re.search(r"^(北海道|東京都|大阪府|京都府|.{2,4}県)", pref)
        pref = m.group(1) if m else pref
    # APIは ProjectName / Project_Name 等のバリエーションがあり得る
    title = _get_child_text(sr, "ProjectName", "projectname", "Project_Name", "project_name", "Title", "title")
    url = _get_child_text(sr, "ExternalDocumentURI", "externaldocumenturi", "URL", "url", "DocumentURI", "documenturi")
    organization = _get_child_text(sr, "OrganizationName", "organizationname", "Organization_Name", "organization_name")
    cft_raw = _get_child_text(sr, "CftIssueDate", "cftissuedate", "Cft_Issue_Date", "cft_issue_date")
    cft_issue_date = ""
    if cft_raw and "T" in cft_raw:
        cft_issue_date = cft_raw.split("T")[0]  # YYYY-MM-DD 部分のみ
    elif cft_raw:
        cft_issue_date = cft_raw[:10] if len(cft_raw) >= 10 else cft_raw
    return {
        "prefecture": pref,
        "title": title or "",
        "url": url or "",
        "organization": organization or "",
        "cft_issue_date": cft_issue_date,
    }


def _fetch_hits_for_date_range(
    query: str,
    date_from: str,
    date_to: str,
    count: int = 1,
    rate_limiter=None,
    deadline_at: Optional[float] = None,
) -> Tuple[Optional[int], bool]:
    """
    指定期間（開始日/終了日）で SearchHits のみ取得。月次件数用。
    Returns: (search_hits or 0, connection_ok).
    """
    _ensure_kkj_deadline(deadline_at)
    if rate_limiter:
        rate_limiter.wait_if_needed()
    _ensure_kkj_deadline(deadline_at)
    # APIガイド: 開始日/終了日 で期間指定
    period = f"{date_from}/{date_to}"
    params = {
        "Query": query,
        "CFT_Issue_Date": period,
        "Count": str(count),
    }
    root = _fetch_kkj_xml(params)
    if root is None:
        return 0, False
    err = _get_error_message(root)
    if err:
        logger.warning("官公需API エラー（期間）: %s", err)
        return 0, True
    hits = _get_search_hits(root)
    return (hits if hits is not None else 0), True


def _fetch_hits_for_query(
    query: str,
    date_from: str,
    count: int = 1,
    rate_limiter=None,
    deadline_at: Optional[float] = None,
) -> Tuple[Optional[int], List[Dict[str, Any]], bool]:
    """
    1回の検索で SearchHits（総件数）と結果リストを返す。
    date_from は 'YYYY-MM-DD' または 'YYYY-MM-DD/'（その日以降）。
    Returns: (search_hits or None, list_of_result_dicts, connection_ok).
    connection_ok が False のときはタイムアウト等でAPIに接続できなかった。
    """
    _ensure_kkj_deadline(deadline_at)
    if rate_limiter:
        rate_limiter.wait_if_needed()
    _ensure_kkj_deadline(deadline_at)
    params = {
        "Query": query,
        "CFT_Issue_Date": date_from if date_from.endswith("/") else date_from + "/",
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
    result_elements = _find_all(root, "SearchResults", "searchresults")
    for sr in result_elements:
        results.append(_get_case_from_result(sr))
    if total and total > 0 and len(results) == 0:
        logger.info("官公需API: SearchHits=%s だが SearchResult を0件しか取得できませんでした。ルートタグ=%s", total, root.tag)
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
        deadline_at = time.monotonic() + _kkj_fetch_deadline_seconds()

        try:
            return self._fetch_trends_within_deadline(
                date_from, as_of, deadline_at
            )
        except KkjFetchDeadlineExceeded:
            logger.warning(
                "⚠️ kkj fetch が %.0fs 以内に終わらなかったため打ち切り（stale cache へ）",
                _kkj_fetch_deadline_seconds(),
            )
            return {
                "success": False,
                "error": "kkj_fetch_deadline",
                "data": None,
            }

    def _fetch_trends_within_deadline(
        self, date_from: str, as_of: str, deadline_at: float
    ) -> Dict[str, Any]:
        # --- Public Sector Signals: キーワード別件数 ---
        signals = []
        connection_ok_count = 0
        keyword_category: Dict[str, str] = {}
        for key, label, query, category_key in SIGNALS_QUERIES:
            total, _, ok = _fetch_hits_for_query(
                query,
                date_from,
                count=1,
                rate_limiter=self.rate_limiter,
                deadline_at=deadline_at,
            )
            if ok:
                connection_ok_count += 1
            keyword_category[key] = category_key
            signals.append({
                "key": key,
                "label": label,
                "count": total if total is not None else 0,
                "trend": "up",
                "category": category_key,
            })

        # --- キーワード別月次件数（直近 SIGNALS_MONTHS ヶ月）---
        signals_monthly: Dict[str, List[Dict[str, Any]]] = {}
        for key, label, query, _ in SIGNALS_QUERIES:
            series: List[Dict[str, Any]] = []
            for y, m in _last_n_months(SIGNALS_MONTHS):
                first, last = _month_range(y, m)
                cnt, ok = _fetch_hits_for_date_range(
                    query,
                    first,
                    last,
                    count=1,
                    rate_limiter=self.rate_limiter,
                    deadline_at=deadline_at,
                )
                if ok:
                    connection_ok_count += 1
                period = f"{y:04d}{m:02d}"
                series.append({"period": period, "value": cnt if cnt is not None else 0})
            series.sort(key=lambda x: (x.get("period") or ""), reverse=True)
            signals_monthly[key] = series
            del series
            gc.collect()

        # --- 都道府県ランキング と キーワード別 注目の案件 Top5 ---
        # キーワード別件数はAPIの「総件数」、県別は「一覧取得した結果」の都道府県別集計。
        # APIは総件数と一覧の返却件数が異なる場合があり、県別の合計は総件数と一致しない。
        prefecture_rankings: Dict[str, List[Dict[str, Any]]] = {}
        keyword_top_cases: Dict[str, List[Dict[str, Any]]] = {}
        ranking_result_count: Dict[str, int] = {}  # 県別集計の元になった一覧取得件数（総件数と異なる場合あり）
        for key, label, query, _ in SIGNALS_QUERIES:
            _, results, ok = _fetch_hits_for_query(
                query,
                date_from,
                count=_ranking_fetch_count(),
                rate_limiter=self.rate_limiter,
                deadline_at=deadline_at,
            )
            if ok:
                connection_ok_count += 1
            ranking_result_count[key] = len(results) if results else 0
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
            # 同一検索結果の先頭5件を「注目の案件 Top5」として保持（案件名・リンク付き）
            seen_urls = set()
            top5 = []
            for r in results:
                if len(top5) >= 5:
                    break
                url = (r.get("url") or "").strip()
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                top5.append({
                    "rank": len(top5) + 1,
                    "title": (r.get("title") or "").strip() or "—",
                    "url": url,
                    "organization": (r.get("organization") or "").strip(),
                    "cft_issue_date": (r.get("cft_issue_date") or "").strip(),
                    "prefecture": (r.get("prefecture") or "").strip(),
                })
            keyword_top_cases[key] = top5
            del results, prefecture_counts, top5, seen_urls
            gc.collect()
        # 後方互換: prefecture_ranking は DX のランキング
        ranking = prefecture_rankings.get("dx", [])

        # 6回中1回も接続できなかった場合は「APIに接続できません」と分かるようにする
        api_unreachable = connection_ok_count == 0
        payload = {
            "signals": signals,
            "signals_monthly": signals_monthly,
            "prefecture_ranking": ranking,
            "prefecture_rankings": prefecture_rankings,
            "keyword_top_cases": keyword_top_cases,
            "ranking_result_count": ranking_result_count,
            "keyword_category": keyword_category,
            "category_labels": dict(KKJ_CATEGORY_LABELS),
            "category_order": list(KKJ_CATEGORY_ORDER),
            "period_days": SIGNALS_DAYS,
            "period_months": SIGNALS_MONTHS,
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

    def _kkj_fill_cache_defaults(self, cached: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """古いキャッシュ行の欠損キーを補う（signals / prefecture_rankings がある前提で呼ぶ）"""
        if cached is None:
            return None
        out = dict(cached)
        if "keyword_top_cases" not in out:
            out["keyword_top_cases"] = {}
        if "ranking_result_count" not in out:
            out["ranking_result_count"] = {}
        if "keyword_category" not in out:
            out["keyword_category"] = {}
        if "category_labels" not in out:
            out["category_labels"] = dict(KKJ_CATEGORY_LABELS)
        if "category_order" not in out:
            out["category_order"] = list(KKJ_CATEGORY_ORDER)
        return out

    def get_public_sector_signals(
        self, force_refresh: bool = False, cache_only: bool = True
    ) -> Dict[str, Any]:
        """
        Public Sector Signals と都道府県ランキングを返す。
        有効なキャッシュがあればそれを返す。cache_only=True のときは外部APIを呼ばず
        キャッシュのみ返す（無い場合は空で返す）。再取得は force_refresh=True のときのみ。
        """
        # API 失敗時のフォールバック用に常に読む（事前クリアはしない）
        stale_before = self._get_from_cache()
        cached = stale_before if not force_refresh else None
        # キャッシュは「キーワード別件数＋県別Top5」の構造があれば有効（0件でも表示用に使う）
        if cached is not None and (cached.get("signals") is not None or cached.get("prefecture_rankings") is not None):
            filled = self._kkj_fill_cache_defaults(cached)
            return {
                "success": True,
                "data": filled,
                "status": "cached",
                "source": "官公需情報ポータルサイト検索API",
            }
        if cache_only and not force_refresh:
            return {
                "success": True,
                "data": {
                    "signals": [],
                    "signals_monthly": {},
                    "prefecture_ranking": [],
                    "prefecture_rankings": {},
                    "keyword_top_cases": {},
                    "ranking_result_count": {},
                    "keyword_category": {},
                    "category_labels": {},
                    "category_order": [],
                    "period_days": 30,
                    "period_months": SIGNALS_MONTHS,
                    "as_of": "",
                },
                "status": "cache_only_empty",
                "source": "官公需情報ポータルサイト検索API",
            }
        result = self._fetch_trends()
        if not result.get("success") and stale_before is not None and (
            stale_before.get("signals") is not None or stale_before.get("prefecture_rankings") is not None
        ):
            filled = self._kkj_fill_cache_defaults(stale_before)
            return {
                "success": True,
                "data": filled,
                "status": "stale_cache_preserved",
                "source": "官公需情報ポータルサイト検索API",
                "message": "官公需APIの取得に失敗したため、保存済みのキャッシュを表示しています。",
                "error": result.get("error"),
            }
        data = result.get("data") if result.get("success") else None
        if data:
            # 0件でもAPI応答はキャッシュする（毎回叩かず表示を安定させる）
            self._save_to_cache(data)
        return result

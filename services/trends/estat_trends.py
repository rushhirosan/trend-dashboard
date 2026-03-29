"""
e-Stat（政府統計の総合窓口）API で景気・マクロ指標を取得するマネージャー
全部入りタブ用に先頭3指標、行政タブ用に全6指標を取得する。
"""

import os
import requests
from typing import Dict, List, Any, Optional
from utils.logger_config import get_logger
from utils.dummy_data_generator import generate_dummy_estat_data
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# e-Stat API ベースURL（v3, JSON）
ESTAT_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"
# 統計ダッシュボードAPI（appId不要・有効求人倍率 季節調整値 全国 月次）
DASHBOARD_BASE = "https://dashboard.e-stat.go.jp/api/1.0/Json"
JOB_RATIO_INDICATOR = "0301020001000010010"  # 有効求人倍率（一般職業紹介状況）
# 消費者物価指数（総合・前年同月比）月次・全国（統計ダッシュボード）
CPI_INDICATOR = "0703010501010090000"
# 新設住宅着工戸数（総戸数）月次・全国（統計ダッシュボード＝2025/2026年データあり）
HOUSING_STARTS_INDICATOR = "0802010103000010000"
# 完全失業率（男女計）月次・全国（統計ダッシュボード）
UNEMPLOYMENT_INDICATOR = "0301010000020020010"
# 実質賃金指数（現金給与総額）月次・全国（統計ダッシュボード）
REAL_WAGES_INDICATOR = "0302030201010090010"
# 小売業販売額（名目）月次・全国（統計ダッシュボード）
RETAIL_SALES_INDICATOR = "0601010201010010000"

# 取得する指標の定義（先頭3件＝全部入りタブ用、以降＝行政タブのみ）
# (indicator_id, name_ja, stats_data_id or None, year_from or None)
# year_from: この年以降のデータのみ採用。None のときは "2026"。
# CPI: 表 0003427113 は月次で返る場合あり。年のみの場合は「2026年」表示になる。
INDICATORS = [
    ("cpi", "消費者物価指数（総合・前年同月比）", "0003427113", None),
    ("job_ratio", "有効求人倍率", None, "2025"),
    ("housing_starts", "住宅着工", "0003119713", "2020"),  # 建築着工時系列（@time が YYYY00MM?? の月次）
    ("unemployment", "完全失業率", None, None),
    ("real_wages", "実質賃金指数", None, None),
    ("retail_sales", "小売業販売額", None, None),
]


class EstatTrendsManager(BaseTrendsManager):
    """e-Stat API で CPI・有効求人倍率・住宅着工を取得するマネージャー"""

    def __init__(self):
        super().__init__(service_name="estat", max_requests=5, window_seconds=60)
        self.app_id = os.getenv("ESTAT_API_KEY") or os.getenv("ESTAT_APP_ID")
        if not self.app_id:
            logger.warning("ESTAT_API_KEY / ESTAT_APP_ID が未設定です。e-Stat API は利用できません。")

    def _get_cache_key(self, *args, **kwargs) -> str:
        return "estat_trends"

    def _get_from_cache(self, *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self.db.get_estat_trends_from_cache()

    def _save_to_cache(self, data: List[Dict[str, Any]], *args, **kwargs) -> bool:
        try:
            return self.db.save_estat_trends_to_cache(data)
        except Exception as e:
            logger.warning("estat キャッシュ保存スキップ（メソッド未実装時）: %s", e)
            return False

    def _clear_cache(self, *args, **kwargs) -> bool:
        try:
            return self.db.clear_estat_trends_cache()
        except Exception as e:
            logger.debug("estat キャッシュクリア: %s", e)
            return False

    def _use_real_data_when_dummy_mode(self) -> bool:
        """USE_DUMMY_DATA=true でも行政データタブでは実データ（e-Stat API/キャッシュ）を使う"""
        return True

    def _generate_dummy_data(self, limit: int = 6, *args, **kwargs) -> list:
        """e-Stat用のダミーデータを生成（indicator_id, name_ja, series 形式）"""
        return generate_dummy_estat_data(limit=limit)

    def _indicator_has_valid_data(self, item: Optional[Dict[str, Any]]) -> bool:
        """1指標分のキャッシュに有効なデータがあるか。あればAPIを呼ばずキャッシュを使う。"""
        if not item or not isinstance(item, dict):
            return False
        if item.get("indicator_id") == "cpi":
            if item.get("cpi_lines") and len(item.get("cpi_lines", [])) > 0:
                return True
            s = item.get("series") or []
            return len(s) > 0
        s = item.get("series") or []
        if len(s) == 0:
            return False
        if item.get("indicator_id") == "housing_starts":
            p = (s[0].get("period") or "")
            if len(p) == 10 and p.endswith("000000"):
                return False
        return True

    def _is_valid_cached_data(self, data: list) -> bool:
        """キャッシュデータがe-Stat形式か検証（name_ja/indicator_id 必須。series または cpi_lines）"""
        if not data or not isinstance(data, list):
            return False
        for item in data:
            if not isinstance(item, dict) or not (item.get("name_ja") or item.get("indicator_id")):
                return False
            if item.get("indicator_id") == "cpi" and item.get("cpi_lines"):
                continue
            if "series" not in item:
                return False
            if item.get("indicator_id") == "housing_starts":
                s = item.get("series") or []
                if s and len(s) > 0:
                    p = (s[0].get("period") or "")
                    if len(p) == 10 and p.endswith("000000"):
                        return False
        return True

    def _stats_list(self, search_word: str, limit: int = 1) -> Optional[str]:
        """getStatsList で検索し、先頭の表の statsDataId を返す。"""
        self.rate_limiter.wait_if_needed()
        url = f"{ESTAT_BASE}/getStatsList"
        params = {"appId": self.app_id, "lang": "J", "searchWord": search_word, "limit": limit}
        try:
            r = requests.get(url, params=params, timeout=25)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("getStatsList 失敗 (%s): %s", search_word, e)
            return None
        inf = data.get("GET_STATS_LIST", {})
        table_inf = inf.get("DATALIST_INF", {}).get("TABLE_INF")
        if not table_inf:
            return None
        one = table_inf[0] if isinstance(table_inf, list) else table_inf
        return one.get("@id")

    def _stats_data(
        self,
        stats_data_id: str,
        max_series: int = 24,
        extra_params: Optional[Dict[str, str]] = None,
        area_only: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """getStatsData で数値を取得し、時系列リスト [{ period, value, unit }] を返す。area_only 指定時はその地域のみ。"""
        self.rate_limiter.wait_if_needed()
        url = f"{ESTAT_BASE}/getStatsData"
        params = {
            "appId": self.app_id,
            "lang": "J",
            "statsDataId": stats_data_id,
            "metaGetFlg": "Y",
            "cntGetFlg": "N",
        }
        if extra_params:
            params.update(extra_params)
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("getStatsData 失敗 (%s): %s", stats_data_id, e)
            return []
        g = data.get("GET_STATS_DATA", {})
        if g.get("RESULT", {}).get("STATUS") != 0:
            return []
        stat_data = g.get("STATISTICAL_DATA", {})
        data_inf = stat_data.get("DATA_INF", {})
        value_list = data_inf.get("VALUE")
        if not value_list:
            return []
        if not isinstance(value_list, list):
            value_list = [value_list]
        # 時系列: 月次は @year+@month で YYYYMM、それ以外は @time/@cat03/@year。同一 period は1件だけ採用。
        def _pick_period(v: dict) -> str:
            year = (v.get("@year") or "").strip()
            month = (v.get("@month") or "").strip()
            if year and month:
                return year + (month.zfill(2) if len(month) <= 2 else month[:2])
            raw = v.get("@time") or v.get("@cat03") or (year if year else "")
            if raw:
                return raw
            # 統計表によっては時間軸が @cat01, @cat02 等の別名で返る場合がある
            for k, val in v.items():
                if k.startswith("@") and isinstance(val, str) and len(val) >= 6 and val.isdigit():
                    return val
            return ""

        def _normalize_period(p: str) -> str:
            """数値のとき YYYYMM に正規化。建築着工は @time が 2024000101（2024年1月）形式なので YYYY+MM にする"""
            if not p or len(p) < 6:
                return p
            if p.isdigit() and len(p) >= 10 and p[4:6] == "00":
                # 2024000101 → 202401（年4桁 + 月2桁）
                return p[:4] + p[6:8]
            if p.isdigit() and len(p) > 6:
                return p[:6]
            return p

        seen_period = set()
        rows = []
        for v in value_list:
            if not isinstance(v, dict):
                continue
            if area_only is not None and (v.get("@area") or "").strip() != area_only:
                continue
            val = v.get("$")
            if val is None or val == "" or (isinstance(val, str) and val.strip() in ("", "*", "-", "x")):
                continue
            period = _pick_period(v)
            if not period:
                continue
            period_norm = _normalize_period(period)
            pkey = period_norm[:6] if len(period_norm) >= 6 and period_norm[:6].isdigit() else period_norm
            if pkey in seen_period:
                continue
            seen_period.add(pkey)
            unit = v.get("@unit") or ""
            rows.append({"period": period_norm or period, "value": val, "unit": unit})
        rows.sort(key=lambda x: (x["period"] or ""), reverse=True)
        return rows[:max_series]

    # 消費者物価指数: 地域別（全国・東京都区部）の前年同月比。e-Stat 地域コードの例
    CPI_AREA_NATIONWIDE = "00000"
    CPI_AREA_TOKYO = "13100"  # 東京都区部（表によっては 13000 等）

    def _stats_data_by_area(
        self,
        stats_data_id: str,
        max_series_per_area: int = 24,
        year_from: str = "2025",
    ) -> Dict[str, List[Dict[str, Any]]]:
        """getStatsData で数値を取得し、地域コード別に時系列リストを返す。"""
        self.rate_limiter.wait_if_needed()
        url = f"{ESTAT_BASE}/getStatsData"
        params = {
            "appId": self.app_id,
            "lang": "J",
            "statsDataId": stats_data_id,
            "metaGetFlg": "Y",
            "cntGetFlg": "N",
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("getStatsData 失敗 (%s): %s", stats_data_id, e)
            return {}
        g = data.get("GET_STATS_DATA", {})
        if g.get("RESULT", {}).get("STATUS") != 0:
            return {}
        data_inf = g.get("STATISTICAL_DATA", {}).get("DATA_INF", {})
        value_list = data_inf.get("VALUE")
        if not value_list:
            return {}
        if not isinstance(value_list, list):
            value_list = [value_list]

        def _pick_period(v: dict) -> str:
            # 月次: @year + @month があれば YYYYMM で返す（表によっては @time が年のみのため）
            year = (v.get("@year") or "").strip()
            month = (v.get("@month") or "").strip()
            if year and month:
                return year + (month.zfill(2) if len(month) <= 2 else month[:2])
            raw = v.get("@time") or v.get("@cat03") or ""
            if raw:
                return raw
            if year:
                return year
            for k, val in v.items():
                if k.startswith("@") and isinstance(val, str) and len(val) >= 6 and val.isdigit():
                    return val
            return ""

        def _normalize_period(p: str) -> str:
            if not p or len(p) < 6:
                return p
            if p.isdigit() and len(p) > 6:
                return p[:6]
            return p

        by_area: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for v in value_list:
            if not isinstance(v, dict):
                continue
            val = v.get("$")
            if val is None or val == "" or (isinstance(val, str) and val.strip() in ("", "*", "-", "x")):
                continue
            period = _pick_period(v)
            if not period:
                continue
            period_norm = _normalize_period(period)
            if (period_norm or "")[:4] < year_from:
                continue
            area = (v.get("@area") or "").strip() or "00000"
            if area not in by_area:
                by_area[area] = {}
            pkey = period_norm[:6] if len(period_norm) >= 6 and period_norm[:6].isdigit() else period_norm
            if pkey in by_area[area]:
                continue
            by_area[area][pkey] = {"period": period_norm or period, "value": val, "unit": v.get("@unit") or ""}

        result: Dict[str, List[Dict[str, Any]]] = {}
        for area, period_dict in by_area.items():
            rows = sorted(period_dict.values(), key=lambda x: (x["period"] or ""), reverse=True)[:max_series_per_area]
            result[area] = rows
        return result

    def _fetch_cpi_tokyo_nationwide(self) -> Dict[str, Any]:
        """東京都区部（速報）・全国（確定）の前年同月比％を取得。"""
        # 表 0003427113 は全国ベースのことが多い。地域別は別表の可能性あり。
        by_area = self._stats_data_by_area("0003427113", max_series_per_area=24, year_from="2025")
        # 地域コードは表により 00000, 0, 13100, 13 等。キーを正規化して全国・東京を判定
        area_names = {"00000": "全国", "0": "全国", "13100": "東京都区部", "13000": "東京都区部", "13": "東京都区部"}
        tokyo_series = []
        nationwide_series = []
        for code, rows in by_area.items():
            name = area_names.get(code) or (code if code != "00000" else "全国")
            if "東京" in name or code in ("13100", "13000", "13"):
                tokyo_series = rows
            elif "全国" in name or code in ("00000", "0"):
                nationwide_series = rows

        def _latest_line(series: list, area_name: str, label_suffix: str) -> Optional[Dict[str, Any]]:
            if not series:
                return None
            s = series[0]
            period = s.get("period") or ""
            val_str = (s.get("value") or "").replace(",", "")
            try:
                val_f = float(val_str)
                pct = round(val_f - 100.0, 1)
            except (ValueError, TypeError):
                pct = None
            y = period[:4] if len(period) >= 4 else ""
            m = period[4:6] if len(period) >= 6 else ""
            period_label = f"{y}年{m}月" if m and m != "00" else f"{y}年"
            return {
                "area": area_name,
                "period": period,
                "period_label": period_label,
                "value": val_str,
                "value_pct": pct,
                "label_suffix": label_suffix,
            }

        tokyo_line = _latest_line(tokyo_series, "東京都区部", "速報")
        nationwide_line = _latest_line(nationwide_series, "全国", "確定")
        if not tokyo_line and not nationwide_line:
            return {}
        # 傾向: 東京と全国の差で簡易表現
        tendency = ""
        if tokyo_line and nationwide_line and tokyo_line.get("value_pct") is not None and nationwide_line.get("value_pct") is not None:
            t = tokyo_line["value_pct"]
            n = nationwide_line["value_pct"]
            if t < n:
                tendency = "東京のコアCPIは2%台を維持しつつも、鈍化の兆しが見え始めている。"
            else:
                tendency = "東京・全国ともコアCPIは2%台で推移。"
        elif tokyo_line or nationwide_line:
            tendency = "東京都区部（速報）と全国（確定）の前年同月比。"
        return {
            "cpi_lines": [x for x in (tokyo_line, nationwide_line) if x],
            "tendency": tendency,
            "series": nationwide_series or tokyo_series,
        }

    def _fetch_job_ratio_from_dashboard(self, year_from: str = "2025") -> List[Dict[str, Any]]:
        """統計ダッシュボードAPIから有効求人倍率（季節調整値・全国月次）を取得。appId不要。"""
        url = f"{DASHBOARD_BASE}/getData"
        params = {
            "Lang": "JP",
            "IndicatorCode": JOB_RATIO_INDICATOR,
            "RegionalRank": "2",  # 全国
            "Cycle": "1",  # 月
            "IsSeasonalAdjustment": "2",  # 季節調整値
            "MetaGetFlg": "N",
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("統計ダッシュボードAPI 有効求人倍率 失敗: %s", e)
            return []
        objs = (
            data.get("GET_STATS", {})
            .get("STATISTICAL_DATA", {})
            .get("DATA_INF", {})
            .get("DATA_OBJ", [])
        )
        if not objs:
            return []
        rows = []
        for item in objs:
            val_obj = item.get("VALUE")
            if not isinstance(val_obj, dict):
                continue
            val = val_obj.get("$")
            if val is None or val == "":
                continue
            t = val_obj.get("@time", "")
            # 20251200 → 202512
            period = t[:6] if len(t) >= 6 and t[:6].isdigit() else t
            if period and period[:4] >= year_from:
                rows.append({"period": period, "value": str(val), "unit": "倍"})
        rows.sort(key=lambda x: (x.get("period") or ""), reverse=True)
        return rows[:24]

    def _fetch_cpi_from_dashboard(self, year_from: str = "2025") -> List[Dict[str, Any]]:
        """統計ダッシュボードAPIから消費者物価指数（総合・前年同月比）全国月次を取得。appId不要。"""
        url = f"{DASHBOARD_BASE}/getData"
        params = {
            "Lang": "JP",
            "IndicatorCode": CPI_INDICATOR,
            "RegionalRank": "2",  # 全国
            "Cycle": "1",  # 月
            "MetaGetFlg": "N",
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("統計ダッシュボードAPI CPI 失敗: %s", e)
            return []
        objs = (
            data.get("GET_STATS", {})
            .get("STATISTICAL_DATA", {})
            .get("DATA_INF", {})
            .get("DATA_OBJ", [])
        )
        if not isinstance(objs, list):
            objs = [objs] if objs else []
        if not objs:
            return []
        # 全国のみ: 同一期間で東京都区部・全国が混在する場合があるため、期間ごとに1件のみ採用
        by_period: Dict[str, Dict[str, Any]] = {}
        for item in objs:
            val_obj = item.get("VALUE")
            if not isinstance(val_obj, dict):
                continue
            val = val_obj.get("$")
            if val is None or val == "":
                continue
            t = val_obj.get("@time", "")
            period = t[:6] if len(t) >= 6 and t[:6].isdigit() else t
            if not period or period[:4] < year_from:
                continue
            if period not in by_period:
                by_period[period] = {"period": period, "value": str(val), "unit": "前年同月=100"}
        rows = sorted(by_period.values(), key=lambda x: (x.get("period") or ""), reverse=True)
        return rows[:24]

    def _fetch_housing_starts_from_dashboard(
        self, year_from: str = "2024", max_series: int = 24
    ) -> List[Dict[str, Any]]:
        """統計ダッシュボードAPIから新設住宅着工戸数（総戸数）月次・全国を取得。2025/2026年データあり。appId不要。"""
        url = f"{DASHBOARD_BASE}/getData"
        params = {
            "Lang": "JP",
            "IndicatorCode": HOUSING_STARTS_INDICATOR,
            "RegionalRank": "2",  # 全国
            "Cycle": "1",  # 月
            "IsSeasonalAdjustment": "1",  # 原数値
            "MetaGetFlg": "N",
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("統計ダッシュボードAPI 住宅着工 失敗: %s", e)
            return []
        objs = (
            data.get("GET_STATS", {})
            .get("STATISTICAL_DATA", {})
            .get("DATA_INF", {})
            .get("DATA_OBJ", [])
        )
        if not isinstance(objs, list):
            objs = [objs] if objs else []
        rows = []
        for item in objs:
            val_obj = item.get("VALUE")
            if not isinstance(val_obj, dict):
                continue
            val = val_obj.get("$") or val_obj.get("\u0024")
            if val is None or val == "":
                continue
            t = (val_obj.get("@time") or "")[:8]
            if len(t) >= 6 and t.isdigit():
                period = t[:4] + t[4:6]  # 20251200 → 202512
                if period[:4] >= year_from:
                    rows.append({"period": period, "value": str(val), "unit": "戸"})
        rows.sort(key=lambda x: (x.get("period") or ""), reverse=True)
        return rows[:max_series]

    def _fetch_dashboard_monthly_series(
        self,
        indicator_code: str,
        unit: str,
        year_from: str = "2024",
        max_series: int = 24,
    ) -> List[Dict[str, Any]]:
        """統計ダッシュボードAPIで月次・全国の系列を取得。appId不要。"""
        url = f"{DASHBOARD_BASE}/getData"
        params = {
            "Lang": "JP",
            "IndicatorCode": indicator_code,
            "RegionalRank": "2",
            "Cycle": "1",
            "IsSeasonalAdjustment": "1",
            "MetaGetFlg": "N",
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("統計ダッシュボードAPI getData 失敗 (%s): %s", indicator_code[:12], e)
            return []
        objs = (
            data.get("GET_STATS", {})
            .get("STATISTICAL_DATA", {})
            .get("DATA_INF", {})
            .get("DATA_OBJ", [])
        )
        if not isinstance(objs, list):
            objs = [objs] if objs else []
        rows = []
        for item in objs:
            val_obj = item.get("VALUE")
            if not isinstance(val_obj, dict):
                continue
            val = val_obj.get("$") or val_obj.get("\u0024")
            if val is None or val == "":
                continue
            t = (val_obj.get("@time") or "")[:8]
            if len(t) >= 6 and t.isdigit():
                period = t[:4] + t[4:6]
                if period[:4] >= year_from:
                    rows.append({"period": period, "value": str(val), "unit": unit})
        rows.sort(key=lambda x: (x.get("period") or ""), reverse=True)
        return rows[:max_series]

    def _fetch_unemployment_from_dashboard(
        self, year_from: str = "2025", max_series: int = 24
    ) -> List[Dict[str, Any]]:
        """完全失業率（男女計）月次・全国。2025年1月以降。"""
        return self._fetch_dashboard_monthly_series(
            UNEMPLOYMENT_INDICATOR, "％", year_from=year_from, max_series=max_series
        )

    def _fetch_real_wages_from_dashboard(
        self, year_from: str = "2025", max_series: int = 24
    ) -> List[Dict[str, Any]]:
        """実質賃金指数（現金給与総額）月次・全国。2020年=100。2025年1月以降。"""
        return self._fetch_dashboard_monthly_series(
            REAL_WAGES_INDICATOR, "2020年=100", year_from=year_from, max_series=max_series
        )

    def _fetch_retail_sales_from_dashboard(
        self, year_from: str = "2025", max_series: int = 24
    ) -> List[Dict[str, Any]]:
        """小売業販売額（名目）月次・全国。単位は億円。2025年1月以降。"""
        return self._fetch_dashboard_monthly_series(
            RETAIL_SALES_INDICATOR, "億円", year_from=year_from, max_series=max_series
        )

    def _fetch_one_indicator(
        self,
        indicator_id: str,
        name_ja: str,
        stats_data_id: Optional[str],
        search_word: Optional[str],
        year_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """1指標分を取得して共通フォーマットで返す。"""
        # CPI: 要約は getStatsData（東京都区部・全国）、月次時系列は統計ダッシュボードを優先
        if indicator_id == "cpi":
            cpi_data = self._fetch_cpi_tokyo_nationwide() if self.app_id else {}
            cpi_lines = list(cpi_data.get("cpi_lines") or [])
            tendency = cpi_data.get("tendency") or ""
            series = self._fetch_cpi_from_dashboard(year_from=year_from or "2025")
            if len(series) < 2:
                series = cpi_data.get("series") or []
            if not cpi_lines and series:
                # appId なしでダッシュボードのみのとき、直近1件で cpi_lines を補う
                s = series[0]
                period = s.get("period") or ""
                y, m = period[:4], period[4:6] if len(period) >= 6 else ""
                period_label = f"{y}年{int(m)}月" if m and m != "00" else f"{y}年"
                try:
                    val_f = float(str(s.get("value") or "").replace(",", ""))
                    pct = round(val_f - 100.0, 1)
                except (ValueError, TypeError):
                    pct = None
                cpi_lines = [{
                    "area": "全国",
                    "period": period,
                    "period_label": period_label,
                    "value": s.get("value"),
                    "value_pct": pct,
                    "label_suffix": "確定",
                }]
            if cpi_lines or series:
                return {
                    "indicator_id": "cpi",
                    "name_ja": name_ja,
                    "unit": "前年同月=100",
                    "series": series,
                    "updated_at": (series[0].get("period") if series else None) or (cpi_lines[0].get("period") if cpi_lines else None),
                    "stats_data_id": "dashboard" if len(series) >= 2 else "0003427113",
                    "cpi_lines": cpi_lines,
                    "tendency": tendency or "東京都区部（速報）と全国（確定）の前年同月比。",
                }
            if self.app_id:
                pass  # 上で処理済み
            # 地域別が取れない場合は従来どおり単一系列
        # 有効求人倍率は統計ダッシュボードAPIから取得（正確な季節調整値）
        if indicator_id == "job_ratio":
            yf = year_from or "2025"
            series = self._fetch_job_ratio_from_dashboard(year_from=yf)
            unit = (series[0].get("unit") or "倍") if series else "倍"
            latest = series[0].get("period") if series else None
            return {
                "indicator_id": indicator_id,
                "name_ja": name_ja,
                "unit": unit,
                "series": series,
                "updated_at": latest,
                "stats_data_id": "dashboard",
            }
        # 住宅着工は統計ダッシュボードを優先（2025/2026年データあり）。失敗時は e-Stat 0003119713
        if indicator_id == "housing_starts":
            series = self._fetch_housing_starts_from_dashboard(
                year_from=year_from or "2024", max_series=24
            )
            if series:
                series.sort(key=lambda x: (x.get("period") or ""), reverse=True)
                total_12m = 0
                for s in series[:12]:
                    try:
                        total_12m += int(str(s.get("value") or "0").replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                housing_extra = {
                    "total_12m": total_12m,
                    "forecast_2026_man": 77.7,
                    "forecast_2026_note": "前年度比+5.5％増と予測",
                }
                return {
                    "indicator_id": indicator_id,
                    "name_ja": name_ja,
                    "unit": (series[0].get("unit") or "戸") if series else "戸",
                    "series": series,
                    "updated_at": series[0].get("period") if series else None,
                    "stats_data_id": "dashboard",
                    **housing_extra,
                }
        # 完全失業率は統計ダッシュボードから取得（appId不要）。2025年1月から。
        if indicator_id == "unemployment":
            series = self._fetch_unemployment_from_dashboard(
                year_from=year_from or "2025", max_series=24
            )
            if series:
                return {
                    "indicator_id": indicator_id,
                    "name_ja": name_ja,
                    "unit": (series[0].get("unit") or "％") if series else "％",
                    "series": series,
                    "updated_at": series[0].get("period") if series else None,
                    "stats_data_id": "dashboard",
                }
        # 実質賃金指数は統計ダッシュボードから取得（appId不要）。2025年1月から。
        if indicator_id == "real_wages":
            series = self._fetch_real_wages_from_dashboard(
                year_from=year_from or "2025", max_series=24
            )
            if series:
                return {
                    "indicator_id": indicator_id,
                    "name_ja": name_ja,
                    "unit": (series[0].get("unit") or "2020年=100") if series else "2020年=100",
                    "series": series,
                    "updated_at": series[0].get("period") if series else None,
                    "stats_data_id": "dashboard",
                }
        # 小売業販売額は統計ダッシュボードから取得（appId不要）。2025年1月から。
        if indicator_id == "retail_sales":
            series = self._fetch_retail_sales_from_dashboard(
                year_from=year_from or "2025", max_series=24
            )
            if series:
                return {
                    "indicator_id": indicator_id,
                    "name_ja": name_ja,
                    "unit": (series[0].get("unit") or "億円") if series else "億円",
                    "series": series,
                    "updated_at": series[0].get("period") if series else None,
                    "stats_data_id": "dashboard",
                }
        sid = stats_data_id
        series = []
        if not sid and search_word:
            sid = self._stats_list(search_word)
        stats_data_kwargs: Dict[str, Any] = {"max_series": 24}
        if indicator_id == "housing_starts":
            stats_data_kwargs["area_only"] = "00000"  # 全国のみ
        if sid:
            series = self._stats_data(sid, **stats_data_kwargs)
            if not series and stats_data_id and search_word:
                sid = self._stats_list(search_word)
                if sid:
                    series = self._stats_data(sid, **stats_data_kwargs)
        if not sid:
            return {
                "indicator_id": indicator_id,
                "name_ja": name_ja,
                "unit": "",
                "series": [],
                "updated_at": None,
                "stats_data_id": None,
                "error": "stats_data_id を取得できませんでした",
            }
        yf = year_from or "2026"
        series = [s for s in series if (s.get("period") or "")[:4] >= yf]
        # 有効求人倍率: 値が 0.3〜5.0 の範囲外なら不正データとみなし除外（誤った統計表の混入防止）
        if indicator_id == "job_ratio" and series:
            valid_series = []
            for s in series:
                try:
                    v = float(str(s.get("value", "")).replace(",", ""))
                    if 0.3 <= v <= 5.0:
                        valid_series.append(s)
                except (ValueError, TypeError):
                    pass
            series = valid_series
            if series:
                series.sort(key=lambda x: (x.get("period") or ""), reverse=True)
        # 住宅着工: period を YYYYMM に正規化し、直近12ヶ月合計・2026年度予測メモを付与
        if indicator_id == "housing_starts" and series:
            for s in series:
                p = s.get("period") or ""
                if len(p) > 6 and p.isdigit():
                    s["period"] = p[:6]
            series.sort(key=lambda x: (x.get("period") or ""), reverse=True)
            total_12m = 0
            for s in series[:12]:
                try:
                    total_12m += int(str(s.get("value") or "0").replace(",", ""))
                except (ValueError, TypeError):
                    pass
            # 2026年度予測: 77.7万戸・前年度比+5.5%（業界予測の目安）
            housing_extra = {
                "total_12m": total_12m,
                "forecast_2026_man": 77.7,
                "forecast_2026_note": "前年度比+5.5％増と予測",
            }
        else:
            housing_extra = {}
        # 単位は先頭の series から
        unit = (series[0].get("unit") or "") if series else ""
        latest_period = series[0].get("period") if series else None
        out = {
            "indicator_id": indicator_id,
            "name_ja": name_ja,
            "unit": unit,
            "series": series,
            "updated_at": latest_period,
            "stats_data_id": sid,
        }
        if housing_extra:
            out.update(housing_extra)
        return out

    def _fetch_trends(
        self, *args, fetch_indicator_ids: Optional[List[str]] = None, **kwargs
    ) -> Dict[str, Any]:
        """fetch_indicator_ids が指定された場合、その指標のみAPI取得（キャッシュありの指標は呼ばない）"""
        if not self.app_id:
            return {
                "success": False,
                "data": [],
                "error": "ESTAT_API_KEY または ESTAT_APP_ID が設定されていません",
                "source": "e-Stat API",
            }
        data = []
        search_words = {
            "job_ratio": "有効求人倍率",
            "housing_starts": "建築着工統計 住宅 月次",
            "unemployment": "労働力調査 完全失業率",
            "real_wages": "現金給与総額 実質",
            "retail_sales": "商業統計 小売業 販売額",
        }
        to_fetch = set(fetch_indicator_ids) if fetch_indicator_ids else None
        for row in INDICATORS:
            indicator_id = row[0]
            if to_fetch is not None and indicator_id not in to_fetch:
                continue
            name_ja = row[1]
            stats_data_id = row[2] if len(row) > 2 else None
            year_from = row[3] if len(row) > 3 else None
            search_word = None if stats_data_id else search_words.get(indicator_id)
            item = self._fetch_one_indicator(
                indicator_id, name_ja, stats_data_id, search_word, year_from=year_from
            )
            data.append(item)
        return {
            "success": True,
            "data": data,
            "status": "api_fetched",
            "source": "e-Stat API",
        }

    def get_trends(
        self,
        limit: int = 6,
        force_refresh: bool = False,
        cache_only: bool = True,
        auto_fetch_on_cache_miss: bool = True,
        sort_key: Optional[str] = None,
        sort_reverse: bool = True,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        そのカテゴリ（指標）においてキャッシュがある場合は外部APIを呼ばない。
        キャッシュがない指標のみAPIで取得し、マージして返す。
        """
        # force_refresh でも事前にキャッシュは破棄しない（API失敗時に直前データを残す）
        if force_refresh:
            logger.info("🔄 estat: force_refresh（全指標を再取得対象にします。事前クリアはしません）")

        cached_list = self._get_from_cache(*args, **kwargs)
        cache_by_id = {}
        if cached_list and isinstance(cached_list, list):
            for it in cached_list:
                iid = it.get("indicator_id")
                if iid:
                    cache_by_id[iid] = it

        indicator_ids = [row[0] for row in INDICATORS]
        if force_refresh:
            need_fetch = list(indicator_ids)
        else:
            need_fetch = [
                iid for iid in indicator_ids
                if not self._indicator_has_valid_data(cache_by_id.get(iid))
            ]

        if not need_fetch and cached_list and not force_refresh:
            logger.info("✅ estat: 全指標キャッシュありのため外部APIを呼ばず返します")
            return {
                "success": True,
                "data": cached_list[:limit],
                "status": "cached",
                "source": "e-Stat API (cache)",
                **kwargs,
            }

        # スケジューラは force_refresh=True のまま cache_only デフォルト True のため、強制更新時は API へ進む
        if cache_only and not force_refresh:
            return {
                "success": True,
                "data": cached_list[:limit] if cached_list else [],
                "status": "cache_only_empty",
                "source": "e-Stat API",
                **kwargs,
            }

        if not self.app_id:
            return {
                "success": False,
                "data": cached_list[:limit] if cached_list else [],
                "error": "ESTAT_API_KEY または ESTAT_APP_ID が設定されていません",
                "source": "e-Stat API",
                **kwargs,
            }

        merged = []
        if need_fetch:
            logger.info("⚠️ estat: %s のみ外部APIで取得します（他はキャッシュ使用）", need_fetch)
            api_result = self._fetch_trends(
                *args, limit=limit, fetch_indicator_ids=need_fetch, **kwargs
            )
            if not api_result.get("success") and cached_list:
                logger.warning("estat: API失敗のため直前キャッシュを返します")
                return {
                    "success": True,
                    "data": (cached_list or [])[:limit],
                    "status": "stale_cache_preserved",
                    "source": "e-Stat API (cache)",
                    "message": "e-Stat APIの取得に失敗したため、保存済みのキャッシュを表示しています。",
                    **kwargs,
                }
            fresh_list = api_result.get("data", []) if api_result.get("success") else []
            fresh_by_id = {it.get("indicator_id"): it for it in fresh_list if it.get("indicator_id")}
            placeholder = lambda iid: {
                "indicator_id": iid,
                "name_ja": next((r[1] for r in INDICATORS if r[0] == iid), iid),
                "series": [],
                "updated_at": None,
                "stats_data_id": None,
            }

            for iid in indicator_ids:
                fresh = fresh_by_id.get(iid)
                cached = cache_by_id.get(iid)
                if self._indicator_has_valid_data(fresh):
                    merged.append(fresh)
                elif self._indicator_has_valid_data(cached):
                    merged.append(cached)
                else:
                    merged.append(fresh or cached or placeholder(iid))

            try:
                self._save_to_cache(merged, *args, **kwargs)
            except Exception as e:
                logger.warning("estat マージ後キャッシュ保存スキップ: %s", e)
        else:
            merged = cached_list or []

        return {
            "success": True,
            "data": merged[:limit],
            "status": "api_fetched" if need_fetch else "cached",
            "source": "e-Stat API",
            **kwargs,
        }

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

# 取得する指標の定義（先頭3件＝全部入りタブ用、以降＝行政タブのみ）
# (indicator_id, name_ja, stats_data_id or None, year_from or None)
# year_from: この年以降のデータのみ採用。None のときは "2026"。
# CPI: 表 0003427113 は月次で返る場合あり。年のみの場合は「2026年」表示になる。
INDICATORS = [
    ("cpi", "消費者物価指数（総合・前年同月比）", "0003427113", None),
    ("job_ratio", "有効求人倍率", None, "2025"),
    ("housing_starts", "住宅着工", "0003119713", "2025"),  # 建築着工 時系列表（月次）
    ("unemployment", "完全失業率", None, None),
    ("real_wages", "実質賃金指数", None, None),
    ("trade", "貿易統計（輸出額）", None, None),
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

    def _generate_dummy_data(self, limit: int = 6, *args, **kwargs) -> list:
        """e-Stat用のダミーデータを生成（indicator_id, name_ja, series 形式）"""
        return generate_dummy_estat_data(limit=limit)

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
    ) -> List[Dict[str, Any]]:
        """getStatsData で数値を取得し、時系列リスト [{ period, value, unit }] を返す。"""
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
        # 時系列: @time を優先し、月次（6桁以上）があればそれを採用。同一 period は1件だけ採用。
        def _pick_period(v: dict) -> str:
            raw = v.get("@time") or v.get("@cat03") or v.get("@year") or ""
            if raw:
                return raw
            # 統計表によっては時間軸が @cat01, @cat02 等の別名で返る場合がある
            for k, val in v.items():
                if k.startswith("@") and isinstance(val, str) and len(val) >= 6 and val.isdigit():
                    return val
            return ""

        def _normalize_period(p: str) -> str:
            """数値のとき YYYYMM に正規化（2026010000 → 202601）して表示を「2026年1月」にする"""
            if not p or len(p) < 6:
                return p
            if p.isdigit() and len(p) > 6:
                return p[:6]
            return p

        seen_period = set()
        rows = []
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

    def _fetch_one_indicator(
        self,
        indicator_id: str,
        name_ja: str,
        stats_data_id: Optional[str],
        search_word: Optional[str],
        year_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """1指標分を取得して共通フォーマットで返す。"""
        # CPI: 東京都区部（速報）・全国（確定）の前年比%形式で取得
        if indicator_id == "cpi" and self.app_id:
            cpi_data = self._fetch_cpi_tokyo_nationwide()
            if cpi_data.get("cpi_lines"):
                series = cpi_data.get("series") or []
                return {
                    "indicator_id": "cpi",
                    "name_ja": name_ja,
                    "unit": "前年同月=100",
                    "series": series,
                    "updated_at": series[0].get("period") if series else None,
                    "stats_data_id": "0003427113",
                    "cpi_lines": cpi_data["cpi_lines"],
                    "tendency": cpi_data.get("tendency") or "",
                }
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
        sid = stats_data_id
        series = []
        if not sid and search_word:
            sid = self._stats_list(search_word)
        if sid:
            series = self._stats_data(sid, max_series=24)
            if not series and stats_data_id and search_word:
                sid = self._stats_list(search_word)
                if sid:
                    series = self._stats_data(sid, max_series=24)
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

    def _fetch_trends(self, *args, **kwargs) -> Dict[str, Any]:
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
            "trade": "貿易統計 輸出額",
        }
        for row in INDICATORS:
            indicator_id = row[0]
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

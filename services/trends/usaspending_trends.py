"""
USAspending API で米国政府支出データを取得するマネージャー
年度別総支出トレンド、機関別支出ランキング、契約/助成金件数・金額、災害関連支出。
PSC/NAICS コードによる Top5 事例（AI/DX/Cyber）の取得。
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

USASPENDING_BASE = "https://api.usaspending.gov/api/v2"

# PSC/NAICS によるカテゴリ定義（キー, 表示ラベル, フィルタ）
# AI: NAICS 541512(システム設計), 541511(プログラミング)
# DX: PSC Service/D (IT & Telecom 全体)
# Cyber: PSC Service/D/DJ (Security & Compliance)
TOP_CASES_QUERIES: List[Tuple[str, str, Dict[str, Any]]] = [
    (
        "ai",
        "AI / IT",
        {"naics_codes": {"require": ["541512", "541511"]}},
    ),
    (
        "dx",
        "DX / IT Services",
        {"psc_codes": {"require": [["Service", "D"]]}},
    ),
    (
        "cyber",
        "Cybersecurity",
        {"psc_codes": {"require": [["Service", "D", "DJ"]]}},
    ),
]

# FIPS 州コード → 州名（主要な州のみ、他はコード表示）
FIPS_TO_STATE: Dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}


class UsaspendingTrendsManager(BaseTrendsManager):
    """USAspending API で政府支出データを取得するマネージャー（APIキー不要）"""

    def __init__(self):
        super().__init__(service_name="usaspending", max_requests=10, window_seconds=60)

    def _get_cache_key(self, *args, **kwargs) -> str:
        return "usaspending_trends"

    def _get_from_cache(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return self.db.get_usaspending_trends_from_cache()

    def _save_to_cache(self, data: Dict[str, Any], *args, **kwargs) -> bool:
        try:
            return self.db.save_usaspending_trends_to_cache(data)
        except Exception as e:
            logger.warning("usaspending キャッシュ保存スキップ: %s", e)
            return False

    def _clear_cache(self, *args, **kwargs) -> bool:
        try:
            return self.db.clear_usaspending_trends_cache()
        except Exception as e:
            logger.debug("usaspending キャッシュクリア: %s", e)
            return False

    def _use_real_data_when_dummy_mode(self) -> bool:
        return True

    def _generate_dummy_data(self, limit: int = 1, *args, **kwargs) -> Dict[str, Any]:
        """USAspending用のダミーデータ"""
        return {
            "total_budget_trend": [
                {"fiscal_year": 2025, "total_budgetary_resources": 13263700405307.76},
                {"fiscal_year": 2024, "total_budgetary_resources": 12248550270454.0},
            ],
            "agency_rankings": [
                {"agency_name": "Department of the Treasury", "amount": 3721993897579},
                {"agency_name": "Department of Health", "amount": 2583134115181},
            ],
            "award_trends": {"contracts": 500000, "grants": 1200000},
            "disaster_overview": {"total": 0, "message": "Sample data"},
            "keyword_top_cases": {
                "ai": [{"rank": 1, "title": "IT System Modernization", "url": "https://www.usaspending.gov/", "organization": "DHS", "obligation_date": "2026-02-01", "state": "VA"}],
                "dx": [],
                "cyber": [],
            },
        }

    def _fetch_total_budget_trend(self) -> List[Dict]:
        """年度別総支出トレンド（FY末=12の値を採用）"""
        self.rate_limiter.wait_if_needed()
        try:
            r = requests.get(
                f"{USASPENDING_BASE}/references/total_budgetary_resources/",
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("USAspending total_budgetary_resources 失敗: %s", e)
            return []

        results = data.get("results", [])
        # FY末（fiscal_period=12）のみを年度別に集約
        by_fy: Dict[int, float] = {}
        for row in results:
            fy = row.get("fiscal_year")
            fp = row.get("fiscal_period")
            val = row.get("total_budgetary_resources", 0)
            if fy and fp == 12:
                by_fy[fy] = val
        rows = [{"fiscal_year": fy, "total_budgetary_resources": amt} for fy, amt in sorted(by_fy.items(), reverse=True)]
        return rows[:10]

    def _fetch_agency_rankings(self, limit: int = 15) -> List[Dict]:
        """機関別支出ランキング"""
        self.rate_limiter.wait_if_needed()
        try:
            r = requests.get(
                f"{USASPENDING_BASE}/reporting/agencies/overview/",
                params={"fiscal_year": 2025, "fiscal_period": 12, "limit": limit},
                timeout=25,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("USAspending agencies/overview 失敗: %s", e)
            return []

        results = data.get("results", [])
        return [
            {
                "rank": i + 1,
                "agency_name": r.get("agency_name", ""),
                "abbreviation": r.get("abbreviation", ""),
                "current_total_budget_authority_amount": r.get("current_total_budget_authority_amount"),
                "obligation_total": r.get("tas_account_discrepancies_totals", {}).get("gtas_obligation_total"),
            }
            for i, r in enumerate(results)
        ]

    def _fetch_award_counts_by_type(self, fiscal_year: int = 2025) -> Dict[str, Any]:
        """契約・助成金等の件数・金額トレンド"""
        self.rate_limiter.wait_if_needed()
        try:
            r = requests.post(
                f"{USASPENDING_BASE}/search/spending_by_award_count/",
                json={"filters": {"time_period": [{"start_date": f"{fiscal_year}-10-01", "end_date": f"{fiscal_year}-09-30"}]}},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("USAspending spending_by_award_count 失敗: %s", e)
            return {}

        return {"fiscal_year": fiscal_year, "results": data}

    def _fetch_disaster_overview(self) -> Dict[str, Any]:
        """災害関連支出の概要"""
        self.rate_limiter.wait_if_needed()
        try:
            r = requests.get(f"{USASPENDING_BASE}/disaster/overview/", timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.debug("USAspending disaster/overview 失敗（スキップ）: %s", e)
            return {"error": str(e), "message": "Disaster data unavailable"}

    def _fips_to_state(self, code: Any) -> str:
        """FIPS 州コードを州略称に変換"""
        if code is None:
            return ""
        s = str(code).strip().zfill(2)
        return FIPS_TO_STATE.get(s, s) if len(s) >= 2 else ""

    def _fetch_top_awards_by_filter(
        self, category_key: str, filters: Dict[str, Any], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        PSC/NAICS フィルタで spending_by_award を検索し、Top N 件を返す。
        Returns: [{"rank", "title", "url", "organization", "obligation_date", "state"}, ...]
        """
        self.rate_limiter.wait_if_needed()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 直近90日
        time_period = [
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            }
        ]
        # award_type_codes は1グループのみ許可。NAICS/PSC は契約向けなので contracts (A,B,C,D) のみ
        payload_filters = {
            **filters,
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": time_period,
        }
        payload = {
            "filters": payload_filters,
            "fields": [
                "Award ID",
                "generated_internal_id",
                "Description",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Base Obligation Date",
                "Place of Performance State Code",
                "Award Amount",
            ],
            "limit": limit,
            "order": "desc",
            "sort": "Base Obligation Date",
        }
        try:
            r = requests.post(
                f"{USASPENDING_BASE}/search/spending_by_award/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("USAspending spending_by_award (%s) 失敗: %s", category_key, e)
            return []

        results = data.get("results", [])
        top_cases: List[Dict[str, Any]] = []
        seen_ids: set = set()
        for i, row in enumerate(results):
            if len(top_cases) >= limit:
                break
            aid = row.get("generated_internal_id") or row.get("Award ID") or ""
            if aid and aid in seen_ids:
                continue
            if aid:
                seen_ids.add(aid)
            title = (row.get("Description") or "").strip() or (row.get("Award ID") or "—")
            agency = (row.get("Awarding Agency") or "").strip()
            sub = (row.get("Awarding Sub Agency") or "").strip()
            if sub and agency:
                agency = f"{agency} / {sub}"
            elif sub:
                agency = sub
            raw_date = row.get("Base Obligation Date") or ""
            obligation_date = raw_date[:10] if raw_date and len(raw_date) >= 10 else raw_date
            state_code = row.get("Place of Performance State Code")
            state = self._fips_to_state(state_code) if state_code is not None else ""
            url = ""
            if aid:
                url = f"https://www.usaspending.gov/award/{aid}/"
            top_cases.append({
                "rank": len(top_cases) + 1,
                "title": title[:200] + ("…" if len(title) > 200 else ""),
                "url": url,
                "organization": agency,
                "obligation_date": obligation_date,
                "state": state,
            })
        return top_cases

    def _fetch_keyword_top_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        """PSC/NAICS で各カテゴリの Top5 事例を取得"""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for key, _label, filters in TOP_CASES_QUERIES:
            cases = self._fetch_top_awards_by_filter(key, filters, limit=5)
            out[key] = cases
        return out

    def _fetch_trends(self, *args, **kwargs) -> Dict[str, Any]:
        """USAspendingから全データを取得"""
        total_trend = self._fetch_total_budget_trend()
        agency_rankings = self._fetch_agency_rankings(15)
        award_trends = self._fetch_award_counts_by_type(2025)
        disaster = self._fetch_disaster_overview()
        keyword_top_cases = self._fetch_keyword_top_cases()

        category_labels = {k: label for k, label, _ in TOP_CASES_QUERIES}
        data = {
            "total_budget_trend": total_trend,
            "agency_rankings": agency_rankings,
            "award_trends": award_trends,
            "disaster_overview": disaster,
            "keyword_top_cases": keyword_top_cases,
            "category_labels": category_labels,
            "category_order": [k for k, _, _ in TOP_CASES_QUERIES],
        }
        return {
            "success": True,
            "data": data,
            "status": "api_fetched",
            "source": "USAspending API",
        }

    def get_trends(
        self,
        limit: int = 1,
        force_refresh: bool = False,
        cache_only: bool = True,
        auto_fetch_on_cache_miss: bool = True,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """USAspendingは data が dict のため、BaseTrendsManager をオーバーライド"""
        if self._is_dummy_mode() and not self._use_real_data_when_dummy_mode():
            return {
                "success": True,
                "data": self._generate_dummy_data(),
                "status": "dummy_generated",
                "source": "dummy",
            }
        cached = self._get_from_cache()
        if force_refresh:
            logger.info("usaspending: force_refresh（事前キャッシュクリアはしません）")
        if cached and not force_refresh:
            return {"success": True, "data": cached, "status": "cached", "source": "USAspending API (cache)"}
        if cache_only and not force_refresh:
            return {"success": True, "data": {}, "status": "cache_only_empty", "source": "USAspending API"}
        api_result = self._fetch_trends()
        if api_result.get("success"):
            data = api_result.get("data", {})
            if data:
                self._save_to_cache(data)
                return {"success": True, "data": data, "status": "api_fetched", "source": "USAspending API"}
        if cached:
            return {
                "success": True,
                "data": cached,
                "status": "stale_cache_preserved",
                "source": "USAspending API (cache)",
                "error": api_result.get("error") if isinstance(api_result, dict) else None,
                "message": "USAspending APIの取得に失敗したかデータが空のため、保存済みのキャッシュを表示しています。",
            }
        return {
            "success": False,
            "data": {},
            "error": api_result.get("error", "Unknown error") if isinstance(api_result, dict) else "Unknown error",
            "status": "api_error",
        }

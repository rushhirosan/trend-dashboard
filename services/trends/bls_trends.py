"""
BLS（米国労働統計局）Public Data API v2 で景気・雇用指標を取得するマネージャー
CPI、失業率、非農業雇用者数、JOLTS、雇用コスト指数、建設業雇用を取得。
"""

import os
import time
import requests
from typing import Dict, List, Any, Optional, Tuple
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# BLS Series IDs（e-Statと同様の指標に対応）
# (indicator_id, name_en, series_id, unit)
BLS_INDICATORS = [
    ("cpi", "CPI (All Items, SA)", "CUSR0000SA0", "1982-84=100"),
    ("unemployment", "Unemployment Rate", "LNS14000000", "%"),
    ("employment", "Total Nonfarm Employment", "CEU0000000001", "thousands"),
    ("jolts_openings", "JOLTS Job Openings", "JTU110099000000000JOL", "thousands"),
    ("jolts_hires", "JOLTS Hires", "JTU110099000000000HIL", "thousands"),
    ("jolts_quits", "JOLTS Quits", "JTU110099000000000QUL", "thousands"),
    ("eci", "Employment Cost Index (Wages)", "CIS1010000000000I", "index"),
    ("construction_emp", "Construction Employment", "CEU2000000001", "thousands"),
]


class BlsTrendsManager(BaseTrendsManager):
    """BLS API で CPI・失業率・雇用数・JOLTS・ECI・建設業雇用を取得するマネージャー"""

    def __init__(self):
        super().__init__(service_name="bls", max_requests=5, window_seconds=60)
        self.api_key = os.getenv("BLS_API_KEY")
        if not self.api_key:
            logger.warning("BLS_API_KEY が未設定です。登録推奨（1日500リクエスト）。未登録は制限あり。")

    def _get_cache_key(self, *args, **kwargs) -> str:
        return "bls_trends"

    def _get_from_cache(self, *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self.db.get_bls_trends_from_cache()

    def _save_to_cache(self, data: List[Dict[str, Any]], *args, **kwargs) -> bool:
        try:
            return self.db.save_bls_trends_to_cache(data)
        except Exception as e:
            logger.warning("bls キャッシュ保存スキップ: %s", e)
            return False

    def _clear_cache(self, *args, **kwargs) -> bool:
        try:
            return self.db.clear_bls_trends_cache()
        except Exception as e:
            logger.debug("bls キャッシュクリア: %s", e)
            return False

    def _use_real_data_when_dummy_mode(self) -> bool:
        """USE_DUMMY_DATA=true でもUS行政データでは実データを使う"""
        return True

    def _generate_dummy_data(self, limit: int = 8, *args, **kwargs) -> list:
        """BLS用のダミーデータを生成"""
        from utils.dummy_data_generator import generate_dummy_bls_data
        return generate_dummy_bls_data(limit=limit)

    def _fetch_bls_series(self, series_ids: List[str], years_back: int = 5) -> Tuple[Dict[str, List[Dict]], Optional[str]]:
        """BLS API から複数シリーズを一括取得。失敗時は空dictと診断用メッセージを返す。"""
        from datetime import datetime

        try:
            max_attempts = max(1, int(os.getenv("BLS_API_MAX_ATTEMPTS", "3")))
        except (ValueError, TypeError):
            max_attempts = 3
        try:
            timeout_sec = max(5, float(os.getenv("BLS_API_TIMEOUT_SECONDS", "45")))
        except (ValueError, TypeError):
            timeout_sec = 45.0

        end_year = datetime.now().year
        start_year = end_year - years_back
        payload = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self.api_key:
            payload["registrationkey"] = self.api_key

        last_detail: Optional[str] = None

        for attempt in range(max_attempts):
            self.rate_limiter.wait_if_needed()
            data = None
            try:
                r = requests.post(
                    BLS_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout_sec,
                )
                if r.status_code == 429 or r.status_code >= 500:
                    last_detail = f"HTTP {r.status_code}"
                    logger.warning(
                        "BLS API HTTP %s (試行 %s/%s): %s",
                        r.status_code,
                        attempt + 1,
                        max_attempts,
                        (r.text or "")[:300],
                    )
                    if attempt < max_attempts - 1:
                        time.sleep(min(60.0, 2.0 ** attempt))
                    continue
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException as e:
                last_detail = str(e)
                logger.warning(
                    "BLS API 失敗 (試行 %s/%s): %s",
                    attempt + 1,
                    max_attempts,
                    e,
                )
                if attempt < max_attempts - 1:
                    time.sleep(min(60.0, 2.0 ** attempt))
                continue
            except ValueError as e:
                last_detail = f"JSON parse error: {e}"
                logger.warning("BLS API 応答がJSONではありません (試行 %s/%s): %s", attempt + 1, max_attempts, e)
                if attempt < max_attempts - 1:
                    time.sleep(min(60.0, 2.0 ** attempt))
                continue

            if not isinstance(data, dict):
                last_detail = "unexpected response type"
                if attempt < max_attempts - 1:
                    time.sleep(min(60.0, 2.0 ** attempt))
                continue

            bls_status = data.get("status")
            if bls_status != "REQUEST_SUCCEEDED":
                msg = data.get("message", "Unknown")
                last_detail = f"BLS status={bls_status!r}, message={msg!r}"
                logger.warning(
                    "BLS API アプリ応答エラー (試行 %s/%s): %s",
                    attempt + 1,
                    max_attempts,
                    last_detail,
                )
                # 日次上限などはリトライしても改善しないが、一時的障害はバックオフで回復することがある
                if attempt < max_attempts - 1:
                    time.sleep(min(60.0, 2.0 ** attempt))
                continue

            result: Dict[str, List[Dict]] = {}
            for s in data.get("Results", {}).get("series", []):
                sid = s.get("seriesID", "")
                if not sid:
                    continue
                rows = []
                for d in s.get("data", []):
                    year = d.get("year", "")
                    period = d.get("period", "")
                    value = d.get("value", "")
                    if not year or not value:
                        continue
                    # period: M01-M12 (month), M13 (annual)
                    if period and period.startswith("M") and len(period) >= 3:
                        m = period[1:3]
                        period_str = f"{year}{m}" if m != "13" else year
                    else:
                        period_str = year
                    rows.append({"period": period_str, "value": value})
                rows.sort(key=lambda x: (x["period"] or ""), reverse=True)
                result[sid] = rows[:24]
            return result, None

        return {}, last_detail

    def _fetch_trends(self, *args, **kwargs) -> Dict[str, Any]:
        """BLSから全指標を取得"""
        series_ids = [row[2] for row in BLS_INDICATORS]
        # BLSは1リクエスト50シリーズまで
        by_series, bls_err = self._fetch_bls_series(series_ids, years_back=5)
        if not by_series:
            err = "BLS API からデータを取得できませんでした"
            if bls_err:
                err = f"{err} ({bls_err})"
            return {
                "success": False,
                "data": [],
                "error": err,
                "source": "BLS API",
            }

        data = []
        for ind_id, name_en, sid, unit in BLS_INDICATORS:
            series = by_series.get(sid, [])
            latest = series[0].get("period") if series else None
            data.append({
                "indicator_id": ind_id,
                "name_en": name_en,
                "unit": unit,
                "series": series,
                "updated_at": latest,
                "series_id": sid,
            })
        return {
            "success": True,
            "data": data,
            "status": "api_fetched",
            "source": "BLS Public Data API v2",
        }

"""check_summary_already_published.py — 二重生成ガードの単体テスト。"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import importlib.util

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_summary_already_published.py"
_SPEC = importlib.util.spec_from_file_location("check_summary_already_published", _SCRIPT)
check = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(check)

JST = ZoneInfo("Asia/Tokyo")


def test_default_daily_id_is_jst_yesterday():
    now = datetime(2026, 8, 27, 9, 0, tzinfo=JST)
    assert check.default_daily_id(now) == "2026-08-26"


def test_default_weekly_id_is_prior_iso_week():
    # 2026-08-27 は木 → 直前終了週は W34（8/17–8/23）の月曜 8/17
    now = datetime(2026, 8, 27, 9, 0, tzinfo=JST)
    assert check.default_weekly_id(now) == "2026-W34"


def test_document_exists_true():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"success": True, "exists": True}
    mock_resp.raise_for_status = lambda: None
    with patch.object(check.requests, "get", return_value=mock_resp) as mock_get:
        assert (
            check.document_exists(
                base_url="https://example.com",
                token="tok",
                kind="daily",
                region="jp",
                doc_id="2026-08-26",
            )
            is True
        )
        mock_get.assert_called_once()


def test_check_both_regions_true():
    with patch.object(check, "document_exists", return_value=True):
        both, statuses = check.check_both_regions(
            base_url="https://example.com",
            token="tok",
            kind="daily",
            doc_id="2026-08-26",
        )
    assert both is True
    assert statuses == {"jp": True, "us": True}


def test_check_both_regions_partial():
    with patch.object(
        check,
        "document_exists",
        side_effect=lambda **kw: kw["region"] == "jp",
    ):
        both, statuses = check.check_both_regions(
            base_url="https://example.com",
            token="tok",
            kind="daily",
            doc_id="2026-08-26",
        )
    assert both is False
    assert statuses["jp"] is True
    assert statuses["us"] is False


def test_check_both_regions_api_error_does_not_skip():
    with patch.object(check, "document_exists", side_effect=RuntimeError("down")):
        both, statuses = check.check_both_regions(
            base_url="https://example.com",
            token="tok",
            kind="daily",
            doc_id="2026-08-26",
        )
    assert both is False
    assert statuses["jp"] is None
    assert statuses["us"] is None

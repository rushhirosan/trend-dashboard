# -*- coding: utf-8 -*-
"""トレンド API の enrich / レスポンス正規化のユニットテスト（DB 不要）"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402

from routes.trend_routes import (  # noqa: E402
    _cache_key_worldnews,
    enrich_trend_payload,
    handle_trend_response,
)


class TestCacheKeyWorldnews:
    def test_lowercases_country(self):
        assert _cache_key_worldnews("US") == "worldnews_trends_us"
        assert _cache_key_worldnews("jp") == "worldnews_trends_jp"

    def test_default_jp(self):
        assert _cache_key_worldnews("") == "worldnews_trends_jp"
        assert _cache_key_worldnews(None) == "worldnews_trends_jp"  # type: ignore[arg-type]


class TestEnrichTrendPayload:
    @patch("routes.trend_routes.TrendsCache")
    def test_adds_cache_as_of_and_row_count(self, mock_tc_class):
        mock_tc = MagicMock()
        mock_tc.get_cache_info.return_value = {
            "last_updated": "2026-03-01T12:00:00+00:00",
            "data_count": 42,
        }
        mock_tc_class.return_value = mock_tc

        r = {"success": True, "data": []}
        enrich_trend_payload(r, {}, cache_key="google_trends")

        assert r["cache_as_of"] == "2026-03-01T12:00:00+00:00"
        assert r["cache_row_count"] == 42
        mock_tc.get_cache_info.assert_called_once_with("google_trends")

    @patch("routes.trend_routes.TrendsCache")
    def test_skips_when_get_cache_info_returns_none(self, mock_tc_class):
        mock_tc = MagicMock()
        mock_tc.get_cache_info.return_value = None
        mock_tc_class.return_value = mock_tc

        r = {"success": True, "data": []}
        enrich_trend_payload(r, {}, cache_key="missing_key")

        assert "cache_as_of" not in r
        assert "cache_row_count" not in r

    def test_empty_list_gets_display_note_when_no_message(self):
        r = {"success": True, "data": [], "status": "fresh"}
        enrich_trend_payload(r, {"success": True, "data": []}, cache_key=None)
        assert "display_note" in r
        assert "表示できるデータがありません" in r["display_note"]

    def test_message_only_display_note_no_default_empty_text(self):
        r = {"success": True, "data": [], "status": "cache_not_found", "message": "no cache"}
        enrich_trend_payload(r, {}, cache_key=None)
        assert r.get("display_note") == "no cache"

    def test_dict_data_not_treated_as_empty(self):
        r = {"success": True, "data": {"records": [1, 2]}}
        enrich_trend_payload(r, {"success": True, "data": {"records": [1, 2]}}, cache_key=None)
        assert "display_note" not in r

    def test_copies_refresh_date_from_result(self):
        r = {"success": True, "data": []}
        enrich_trend_payload(
            r,
            {"success": True, "data": [], "refresh_date": "2026-03-15"},
            cache_key=None,
        )
        assert r.get("refresh_date") == "2026-03-15"


class TestHandleTrendResponse:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        return app

    @patch("routes.trend_routes.TrendsCache")
    def test_success_json_shape(self, mock_tc_class, app):
        mock_tc_class.return_value.get_cache_info.return_value = None

        with app.app_context():
            resp = handle_trend_response(
                {
                    "success": True,
                    "data": [{"title": "a"}],
                    "status": "fresh",
                    "source": "Test API",
                },
                "fallback error",
                default_source="Default",
                cache_key="google_trends",
            )

        data = json.loads(resp.get_data(as_text=True))
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["source"] == "Test API"

    @patch("routes.trend_routes.TrendsCache")
    def test_list_result_backward_compat(self, mock_tc_class, app):
        mock_tc_class.return_value.get_cache_info.return_value = None

        with app.app_context():
            resp = handle_trend_response(
                [{"x": 1}],
                "err",
                default_source="ListSrc",
                cache_key=None,
            )

        data = json.loads(resp.get_data(as_text=True))
        assert data["success"] is True
        assert data["data"] == [{"x": 1}]
        assert data["status"] == "fresh"

    @patch("routes.trend_routes.TrendsCache")
    def test_cache_not_found_200(self, mock_tc_class, app):
        mock_tc_class.return_value.get_cache_info.return_value = None

        with app.app_context():
            resp, status = handle_trend_response(
                {
                    "success": False,
                    "status": "cache_not_found",
                    "data": [],
                    "error": "キャッシュにデータがありません",
                },
                "err",
                default_source="X",
                cache_key="qiita_trends",
            )

        assert status == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["success"] is True
        assert data["status"] == "cache_not_found"

    @patch("routes.trend_routes.TrendsCache")
    def test_api_failure_500(self, mock_tc_class, app):
        mock_tc_class.return_value.get_cache_info.return_value = None

        with app.app_context():
            resp, status = handle_trend_response(
                {
                    "success": False,
                    "error": "upstream failed",
                },
                "err",
                cache_key=None,
            )

        assert status == 500
        data = json.loads(resp.get_data(as_text=True))
        assert data["success"] is False
        assert "upstream failed" in data["error"]

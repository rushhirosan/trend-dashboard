"""Tests for scripts/generate_ai_daily_summary.py (date helper + API fetch)."""

import importlib.util
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_ai_daily_summary.py"


@pytest.fixture(scope="module")
def gads():
    spec = importlib.util.spec_from_file_location("generate_ai_daily_summary", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_business_day_jst_is_yesterday(gads):
    from zoneinfo import ZoneInfo

    jst = ZoneInfo("Asia/Tokyo")
    noon = datetime(2026, 5, 11, 12, 0, tzinfo=jst)
    assert gads.default_business_day_jst(noon) == date(2026, 5, 10)

    before_7 = datetime(2026, 5, 11, 6, 0, tzinfo=jst)
    assert gads.default_business_day_jst(before_7) == date(2026, 5, 10)


def test_fetch_snapshots_from_api_parses_success_payload(gads, monkeypatch):
    bd = date(2026, 5, 10)
    sample = [
        {
            "slot": "07",
            "series_key": "google_trends_jp",
            "items": [{"t": "alpha", "r": 1}],
            "captured_at": "2026-05-10T07:05:00+09:00",
        }
    ]

    def fake_get(url, **_kwargs):
        assert "business_day=2026-05-10" in url
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"success": True, "data": sample}
        return r

    monkeypatch.setattr(gads.requests, "get", fake_get)
    rows = gads.fetch_snapshots_from_api("https://example.com", bd, timeout=30)
    assert rows == sample


@pytest.mark.parametrize(
    "gha,db,cli,expected",
    [
        (False, "postgresql://x/trends-db.flycast:5432/db", False, False),
        ("true", "postgresql://x/trends-db.flycast:5432/db", False, True),
        ("true", "postgresql://h/db.internal:5432/db", False, True),
        ("true", "postgresql://localhost/db", False, False),
        ("true", "postgresql://x/trends-db.flycast/db", True, True),
        (False, "", True, True),
    ],
)
def test_use_http_snapshots_gha_fly_private_fallback(monkeypatch, gads, gha, db, cli, expected):
    if gha is False:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    else:
        monkeypatch.setenv("GITHUB_ACTIONS", gha)
    assert gads.use_http_snapshots(cli_from_api=cli, database_url=db) is expected

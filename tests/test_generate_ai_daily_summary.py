"""Tests for scripts/generate_ai_daily_summary.py (date helper + API fetch)."""

import importlib.util
import json
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


@pytest.mark.parametrize(
    "series_key,expected",
    [
        ("nhk_jp", "ニュース"),
        ("google_trends_jp", "検索・動画"),
        ("youtube_trends_us", "検索・動画"),
        ("zenn_jp", "テック・開発"),
        ("jpcert_jp", "テック・開発"),
        ("stock_jp", "マーケット"),
        ("book_jp_fiction", "エンタメ"),
        ("estat_jp", "行政"),
        ("kkj_jp", "行政"),
    ],
)
def test_categorize_series_key(gads, series_key, expected):
    assert gads.categorize_series_key(series_key) == expected


def test_compact_rows_by_category_groups_series(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "google_trends_jp",
            "items": [{"t": "kw", "r": 1}],
            "captured_at": "2026-05-17T07:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-17T19:00:00+09:00",
        },
    ]
    payload = gads.compact_rows_by_category(rows)
    headings = [c["category"] for c in payload["categories"]]
    assert headings == list(gads.SUMMARY_CATEGORY_ORDER)
    news = next(c for c in payload["categories"] if c["category"] == "ニュース")
    search = next(c for c in payload["categories"] if c["category"] == "検索・動画")
    slot19 = next(s for s in news["slots"] if s["slot"] == "19")
    slot07 = next(s for s in search["slots"] if s["slot"] == "07")
    assert slot19["series"][0]["series_key"] == "nhk_jp"
    assert slot07["series"][0]["series_key"] == "google_trends_jp"


def test_write_generation_status_json(tmp_path, gads):
    bd = date(2026, 6, 1)
    daily_dir = tmp_path / "daily"
    p = gads.write_generation_status(
        bd,
        ok=True,
        daily_dir=daily_dir,
        markdown="docs/summaries/daily/2026-06-01.md",
        model="gpt-4o-mini",
        snapshot_row_count=42,
    )
    assert p.name == "2026-06-01.generation.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["business_day"] == "2026-06-01"
    assert data["ok"] is True
    assert data["snapshot_row_count"] == 42
    assert "logged_at" in data

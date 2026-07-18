"""サマリー原稿の DB 公開経路（summary_store 優先・ファイル fallback・upsert API）のテスト"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask import Flask

from services.summary import summary_pages, summary_store

JST = timezone(timedelta(hours=9))


def _daily_md(business_day: str, one_liner: str, status: str = "draft") -> str:
    return f"""---
status: {status}
generator: openai
business_day: "{business_day}"
snapshot_slots_included: ["07", "13", "19", "01"]
---

# 日次サマリー — {business_day}

## 昨日の一行結論

{one_liner}

## 📈 昨日いちばん動いた3つ

1. [Topic A](https://example.com/a)（Source）
"""


@pytest.fixture
def daily_dir(tmp_path, monkeypatch):
    d = tmp_path / "daily"
    d.mkdir()
    monkeypatch.setattr(summary_pages, "_DAILY_DIR", d)
    # 既定では DB は空（= ファイル fallback）
    monkeypatch.setattr(summary_store, "get_document", lambda *a, **k: None)
    monkeypatch.setattr(summary_store, "list_documents", lambda *a, **k: [])
    return d


def _recent_day(days_ago: int = 1) -> str:
    return (datetime.now(JST).date() - timedelta(days=days_ago)).isoformat()


def test_load_daily_page_falls_back_to_file(daily_dir):
    day = _recent_day()
    (daily_dir / f"{day}.md").write_text(_daily_md(day, "ファイル版の一行結論です。"), encoding="utf-8")

    page = summary_pages.load_daily_page(day, region="jp", allow_draft=True)
    assert page is not None
    assert "ファイル版の一行結論です。" in page["one_liner"]


def test_load_daily_page_prefers_db(daily_dir, monkeypatch):
    day = _recent_day()
    (daily_dir / f"{day}.md").write_text(_daily_md(day, "ファイル版の一行結論です。"), encoding="utf-8")
    monkeypatch.setattr(
        summary_store,
        "get_document",
        lambda kind, region, doc_id: _daily_md(day, "DB版の一行結論です。"),
    )

    page = summary_pages.load_daily_page(day, region="jp", allow_draft=True)
    assert page is not None
    assert "DB版の一行結論です。" in page["one_liner"]


def test_load_daily_page_outside_retention_returns_none(daily_dir):
    old_day = _recent_day(days_ago=30)
    (daily_dir / f"{old_day}.md").write_text(_daily_md(old_day, "古い原稿です。"), encoding="utf-8")

    assert summary_pages.load_daily_page(old_day, region="jp", allow_draft=True) is None


def test_list_published_merges_db_and_filters_retention(daily_dir, monkeypatch):
    recent_file = _recent_day(days_ago=2)
    old_file = _recent_day(days_ago=30)
    db_only = _recent_day(days_ago=1)
    (daily_dir / f"{recent_file}.md").write_text(_daily_md(recent_file, "ファイル分。"), encoding="utf-8")
    (daily_dir / f"{old_file}.md").write_text(_daily_md(old_file, "期限切れ分。"), encoding="utf-8")
    monkeypatch.setattr(
        summary_store,
        "list_documents",
        lambda kind, region: [
            (db_only, _daily_md(db_only, "DBのみの分。"), datetime.now(JST))
        ],
    )

    ids = [d for d, _ in summary_pages.list_published_daily(region="jp", allow_draft=True)]
    assert ids == sorted([recent_file, db_only], reverse=True)
    assert old_file not in ids


# --- upsert API ---------------------------------------------------------

@pytest.fixture
def client():
    from routes.data_routes import data_bp

    app = Flask(__name__)
    app.register_blueprint(data_bp)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


_PAYLOAD = {
    "kind": "daily",
    "region": "jp",
    "id": "2026-07-17",
    "body_md": "---\nstatus: draft\ngenerator: openai\n---\n\n本文",
}


def test_upsert_endpoint_disabled_without_token(client, monkeypatch):
    monkeypatch.delenv("SUMMARY_UPSERT_TOKEN", raising=False)
    res = client.post("/api/summaries/documents", json=_PAYLOAD)
    assert res.status_code == 503


def test_upsert_endpoint_rejects_bad_token(client, monkeypatch):
    monkeypatch.setenv("SUMMARY_UPSERT_TOKEN", "secret-token")
    res = client.post(
        "/api/summaries/documents",
        json=_PAYLOAD,
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 401


def test_upsert_endpoint_validates_payload(client, monkeypatch):
    monkeypatch.setenv("SUMMARY_UPSERT_TOKEN", "secret-token")
    res = client.post(
        "/api/summaries/documents",
        json={**_PAYLOAD, "id": "not-a-date"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert res.status_code == 400


@patch("services.summary.summary_store.upsert_document", return_value=True)
def test_upsert_endpoint_success(mock_upsert, client, monkeypatch):
    monkeypatch.setenv("SUMMARY_UPSERT_TOKEN", "secret-token")
    res = client.post(
        "/api/summaries/documents",
        json=_PAYLOAD,
        headers={"Authorization": "Bearer secret-token"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    mock_upsert.assert_called_once_with("daily", "jp", "2026-07-17", _PAYLOAD["body_md"])


def test_weekly_monday_parsing():
    assert summary_store.weekly_monday("2026-W29") == date(2026, 7, 13)
    assert summary_store.weekly_monday("invalid") is None

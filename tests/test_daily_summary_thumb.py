"""日次サムネは一覧と詳細で同じ static ファイルを指す。"""

from services.summary.summary_pages import daily_thumb_filename, daily_thumb_url

# リポジトリに残っている日次サムネ（保持期間外の固定日付は使わない）
_KNOWN_DAY = "2026-11-18"


def test_daily_thumb_filename_jp_known_day():
    path = daily_thumb_filename(_KNOWN_DAY, "jp")
    assert path == f"images/summaries/daily/jp/{_KNOWN_DAY}.png"


def test_daily_thumb_filename_missing_day():
    assert daily_thumb_filename("2026-01-01", "jp") is None


def test_daily_thumb_filename_us_known_day():
    path = daily_thumb_filename(_KNOWN_DAY, "us")
    assert path == f"images/summaries/daily/us/{_KNOWN_DAY}.png"


def test_daily_thumb_filename_rejects_bad_id():
    assert daily_thumb_filename("2026-W43", "jp") is None


def test_daily_thumb_url_points_at_shared_route():
    assert daily_thumb_url(_KNOWN_DAY, "jp") == f"/summaries/daily/{_KNOWN_DAY}/thumb"
    assert daily_thumb_url(_KNOWN_DAY, "us") == f"/us/summaries/daily/{_KNOWN_DAY}/thumb"


def test_daily_thumb_url_missing_day(monkeypatch):
    monkeypatch.setattr(
        "services.summary.summary_store.has_thumb",
        lambda *args, **kwargs: False,
    )
    assert daily_thumb_url("2026-01-01", "jp") is None


def test_daily_thumb_url_uses_db_when_file_is_absent(monkeypatch):
    monkeypatch.setattr(
        "services.summary.summary_store.has_thumb",
        lambda *args, **kwargs: True,
    )
    assert daily_thumb_url("2026-01-01", "jp") == "/summaries/daily/2026-01-01/thumb"

"""日次サムネは一覧と詳細で同じ static ファイルを指す。"""

from services.summary.summary_pages import daily_thumb_filename, daily_thumb_url


def test_daily_thumb_filename_jp_known_day():
    path = daily_thumb_filename("2026-10-25", "jp")
    assert path == "images/summaries/daily/jp/2026-10-25.jpg"


def test_daily_thumb_filename_missing_day():
    assert daily_thumb_filename("2026-01-01", "jp") is None


def test_daily_thumb_filename_us_known_day():
    path = daily_thumb_filename("2026-10-25", "us")
    assert path == "images/summaries/daily/us/2026-10-25.jpg"


def test_daily_thumb_filename_rejects_bad_id():
    assert daily_thumb_filename("2026-W43", "jp") is None


def test_daily_thumb_url_points_at_shared_route():
    assert daily_thumb_url("2026-10-25", "jp") == "/summaries/daily/2026-10-25/thumb"
    assert daily_thumb_url("2026-10-25", "us") == "/us/summaries/daily/2026-10-25/thumb"


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

"""日次サムネは一覧と詳細で同じ static ファイルを指す。"""

from services.summary.summary_pages import daily_thumb_filename


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

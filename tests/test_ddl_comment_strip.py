"""database_config の DDL コメント除去（apply_init に関連）"""

from database_config import _strip_leading_line_comments


def test_strip_leading_comment_before_create():
    raw = """
                -- 7時起点の business_day ごとのスナップショット
                CREATE TABLE IF NOT EXISTS trend_daily_snapshots (
                    id BIGSERIAL PRIMARY KEY
                );
    """
    out = _strip_leading_line_comments(raw.strip())
    assert out.startswith("CREATE TABLE")
    assert "-- 7時起点" not in out.split("\n")[0]


def test_strip_multiple_blank_and_comment_lines():
    raw = "\n\n-- note\n-- another\nSELECT 1"
    assert _strip_leading_line_comments(raw) == "SELECT 1"


def test_empty_after_comments():
    assert _strip_leading_line_comments("-- only\n-- comments") == ""

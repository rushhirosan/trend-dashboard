"""いまの1位文（SEO / AI が引用する先頭文）"""

from datetime import datetime

import pytz

from services.ssr_data import build_now_ranking

JST = pytz.timezone("Asia/Tokyo")
# 20:30 JST は直近版が 19時
NOW = datetime(2026, 10, 17, 20, 30, tzinfo=JST)


def test_jp_sentence_lists_three_number_ones():
    got = build_now_ranking(
        {
            "news": [{"title": "台風のニュース"}],
            "youtube": [{"title": "紹介映像"}],
            "google": [{"keyword": "検索語"}],
        },
        variant="jp",
        now=NOW,
    )
    assert got["title"] == "いまの日本トレンド順位 | トレンドダッシュボード"
    assert got["sentence"] == (
        "10月17日 19時（JST）の日本。"
        "ニュース1位は「台風のニュース」、YouTube1位は「紹介映像」、Googleトレンド1位は「検索語」。"
    )
    assert got["description"] == got["sentence"]


def test_jp_sentence_skips_missing_sources():
    got = build_now_ranking(
        {"youtube": [{"title": "動画だけ"}]},
        variant="jp",
        now=NOW,
    )
    assert "YouTube1位は「動画だけ」" in got["sentence"]
    assert "ニュース1位" not in got["sentence"]
    assert "Googleトレンド1位" not in got["sentence"]


def test_jp_sentence_without_data_still_states_ranks():
    got = build_now_ranking({}, variant="jp", now=NOW)
    assert "10月17日 19時（JST）の日本のトレンド順位" in got["sentence"]
    assert "1位" in got["sentence"]
    assert "「」" not in got["sentence"]


def test_us_sentence_prefers_cnn_and_quotes_ranks():
    got = build_now_ranking(
        {
            "cnn": [{"title": "CNN lead"}],
            "worldnews": [{"title": "Wire lead"}],
            "youtube": [{"title": "A video"}],
            "google": [{"keyword": "search term"}],
        },
        variant="us",
        now=NOW,
    )
    assert got["title"] == "Current U.S. trend ranks | Trends Dashboard"
    assert got["sentence"].startswith("Oct 17, 19:00 JST. Current U.S. trends: ")
    assert 'news #1 is "CNN lead"' in got["sentence"]
    assert "Wire lead" not in got["sentence"]
    assert 'YouTube #1 is "A video"' in got["sentence"]
    assert 'Google Trends #1 is "search term"' in got["sentence"]


def test_rank_name_strips_quotes_and_truncates():
    long_title = "あ" * 50
    got = build_now_ranking(
        {"news": [{"title": f"「{long_title}」"}]},
        variant="jp",
        now=NOW,
    )
    assert "「「" not in got["sentence"]
    assert "…" in got["sentence"]
    assert "あ" * 50 not in got["sentence"]

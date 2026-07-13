"""summary_pages のユニットテスト（一行結論の文分割・リンク化など表示ロジック）"""

from services.summary.summary_pages import (
    _collect_topic_links,
    _linkify,
    _split_sentences,
)

_BODY = """## 📈 昨日いちばん動いた3つ

1. [Bonnie Tyler](https://en.wikipedia.org/wiki/Bonnie_Tyler)（Wikipedia (EN)）

## 📊 カテゴリ別トップ3

### ニュース
1. [高市首相の意向にひた走る思惑は 「チームコバタカ」が描くシナリオ](https://www.asahi.com/articles/x.html)（World News）
2. [山瀬まみ](https://ja.wikipedia.org/wiki/x)（Wikipedia）
"""


def test_split_sentences_basic():
    text = "一文目です。二文目です。三文目です。"
    assert _split_sentences(text) == [
        "一文目です。",
        "二文目です。",
        "三文目です。",
    ]


def test_split_sentences_keeps_inner_punctuation():
    # 括弧や矢印を含む実データ相当。句点でのみ分割される。
    text = (
        "複数の取得元で「One Two」が重なった（7時4位 → 13時2位 → 19時3位）。"
        "順位の動きが大きかったのは「Bonnie Tyler」と「山瀬まみ」。"
    )
    assert _split_sentences(text) == [
        "複数の取得元で「One Two」が重なった（7時4位 → 13時2位 → 19時3位）。",
        "順位の動きが大きかったのは「Bonnie Tyler」と「山瀬まみ」。",
    ]


def test_split_sentences_empty():
    assert _split_sentences("") == []
    assert _split_sentences("   ") == []


def test_split_sentences_no_terminal_period():
    # 末尾に句点が無くても1文として返す。
    assert _split_sentences("句点なしの文") == ["句点なしの文"]


def test_collect_topic_links_dedup_and_sorted():
    links = _collect_topic_links(_BODY)
    labels = [label for label, _ in links]
    # 長いラベルが先（longest-match 用）
    assert labels[0] == "高市首相の意向にひた走る思惑は 「チームコバタカ」が描くシナリオ"
    assert set(labels) == {
        "高市首相の意向にひた走る思惑は 「チームコバタカ」が描くシナリオ",
        "Bonnie Tyler",
        "山瀬まみ",
    }


def test_linkify_wraps_known_topics():
    links = _collect_topic_links(_BODY)
    html = str(_linkify("順位の動きが大きかったのは「Bonnie Tyler」と「山瀬まみ」。", links))
    assert '<a href="https://en.wikipedia.org/wiki/Bonnie_Tyler"' in html
    assert '<a href="https://ja.wikipedia.org/wiki/x"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener nofollow"' in html


def test_linkify_leaves_unknown_topics_plain():
    links = _collect_topic_links(_BODY)
    html = str(_linkify("複数の取得元で「One Two」が重なった。", links))
    assert "<a " not in html
    assert "「One Two」" in html


def test_linkify_escapes_plain_text():
    html = str(_linkify("a < b & c", []))
    assert "&lt;" in html and "&amp;" in html
    assert "<a " not in html


def test_linkify_prefers_longest_match():
    links = _collect_topic_links(_BODY)
    html = str(_linkify("ニュースでは「高市首相の意向にひた走る思惑は 「チームコバタカ」が描くシナリオ」が上位。", links))
    assert '<a href="https://www.asahi.com/articles/x.html"' in html
    # 長いラベル全体が1つのリンクになる
    assert html.count("<a ") == 1

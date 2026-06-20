"""memory_trim ユーティリティのテスト。"""

from utils.memory_trim import try_release_rss


def test_try_release_rss_does_not_raise():
    assert try_release_rss(collect=False) in (True, False)

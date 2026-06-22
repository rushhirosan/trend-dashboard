"""JP refresh タスクの重量分散分割。"""

from utils.jp_refresh_chunks import (
    expected_jp_result_key_count_from_env,
    partition_jp_refresh_tasks,
    select_jp_refresh_tasks,
)


def test_partition_spreads_heavy_sources():
    tasks = [
        ("google", None, "JP"),
        ("rakuten", None, "JP"),
        ("hatena", None, "JP"),
        ("note", None, "JP"),
        ("kkj", None, "JP"),
        ("openalex", None, "JP"),
        ("openalex", None, "JP"),
        ("youtube", None, "JP"),
    ]
    parts = partition_jp_refresh_tasks(tasks, 4)
    assert len(parts) == 4
    assert sum(len(p) for p in parts) == len(tasks)
    chunk_keys = [sorted({t[0] for t in part}) for part in parts]
    note_chunks = [i for i, keys in enumerate(chunk_keys) if "note" in keys]
    kkj_chunks = [i for i, keys in enumerate(chunk_keys) if "kkj" in keys]
    assert len(note_chunks) == 1
    assert len(kkj_chunks) == 1
    assert note_chunks != kkj_chunks


def test_select_jp_refresh_tasks_covers_all():
    tasks = [("a", None, "JP"), ("b", None, "JP"), ("c", None, "JP"), ("d", None, "JP")]
    merged = []
    for i in range(1, 3):
        merged.extend(select_jp_refresh_tasks(tasks, i, 2))
    assert len(merged) == len(tasks)
    assert {t[0] for t in merged} == {t[0] for t in tasks}


def test_kkj_isolated_when_six_chunks():
    tasks = [
        ("google", None, "JP"),
        ("rakuten", None, "JP"),
        ("hatena", None, "JP"),
        ("note", None, "JP"),
        ("kkj", None, "JP"),
        ("openalex", None, "JP"),
        ("youtube", None, "JP"),
    ]
    parts = partition_jp_refresh_tasks(tasks, 6)
    kkj_parts = [i for i, part in enumerate(parts) if any(t[0] == "kkj" for t in part)]
    assert len(kkj_parts) == 1
    kkj_part = parts[kkj_parts[0]]
    assert len(kkj_part) == 1
    assert kkj_part[0][0] == "kkj"


def test_expected_jp_key_count_without_twitch(monkeypatch):
    monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
    assert expected_jp_result_key_count_from_env() == 26

"""JP refresh タスクの subprocess 分割（重量源の分散）。"""

from __future__ import annotations

_JP_HEAVY_SINGLE_KEYS = frozenset({"rakuten", "hatena", "note", "kkj"})
_JP_HEAVY_MULTI_KEYS = frozenset({"openalex", "book", "twitch"})
# chunk_count が十分なとき単独 subprocess にする（create_app 二重 + kkj 等の RSS ピーク対策）
_JP_ISOLATE_KEYS = ("kkj", "note")


def _isolate_key_for_chunk_count(key: str, chunk_count: int) -> bool:
    if key not in _JP_ISOLATE_KEYS:
        return False
    if key == "kkj":
        return chunk_count >= 5
    if key == "note":
        return chunk_count >= 6
    return False


def expected_jp_result_key_count(tasks: list) -> int:
    """refresh 結果 dict に含まれるべき JP ソースキー数（book/openalex 等は1キーに集約）。"""
    return len({task[0] for task in tasks})


def expected_jp_result_key_count_from_env() -> int:
    """本番と同条件の JP 源数（Twitch 認証の有無で ±1）。"""
    import os

    keys = [
        "google", "youtube", "music", "worldnews", "podcast", "rakuten", "hatena",
        "qiita", "nhk", "prtimes", "prtimes_hatena", "stock", "crypto", "movie",
        "book", "github", "appstore", "ipa", "jpcert", "zenn", "note", "wikipedia",
        "estat", "kkj", "bluesky", "openalex",
    ]
    if os.getenv("TWITCH_CLIENT_ID") and os.getenv("TWITCH_CLIENT_SECRET"):
        keys.append("twitch")
    return len(keys)


def partition_jp_refresh_tasks(tasks: list, chunk_count: int) -> list[list]:
    """JP タスクを chunk_count 個の subprocess 用バケットへ分散。"""
    if chunk_count <= 1:
        return [tasks]
    buckets: list[list] = [[] for _ in range(chunk_count)]
    isolated: list = []
    singles: list = []
    multis: dict[str, list] = {}
    rest: list = []
    for task in tasks:
        key = task[0]
        if _isolate_key_for_chunk_count(key, chunk_count):
            isolated.append(task)
        elif key in _JP_HEAVY_SINGLE_KEYS:
            singles.append(task)
        elif key in _JP_HEAVY_MULTI_KEYS:
            multis.setdefault(key, []).append(task)
        else:
            rest.append(task)
    idx = 0
    isolated_bucket_ids: set[int] = set()
    for task in isolated:
        buckets[idx].append(task)
        isolated_bucket_ids.add(idx)
        idx += 1
    free_buckets = [i for i in range(chunk_count) if i not in isolated_bucket_ids]
    if not free_buckets:
        free_buckets = list(range(chunk_count))
    free_idx = 0

    def _append_rotating(task) -> None:
        nonlocal free_idx
        bucket_id = free_buckets[free_idx % len(free_buckets)]
        buckets[bucket_id].append(task)
        free_idx += 1

    for task in singles:
        _append_rotating(task)
    for key in ("openalex", "book", "twitch"):
        for task in multis.get(key, []):
            _append_rotating(task)
    for task in rest:
        _append_rotating(task)
    return buckets


def select_jp_refresh_tasks(tasks: list, chunk_index: int | None, chunk_count: int | None) -> list:
    """chunk_index（1始まり）に対応する JP タスク部分集合。"""
    if chunk_index is None or chunk_count is None or chunk_count <= 1:
        return tasks
    if chunk_index < 1 or chunk_index > chunk_count:
        raise ValueError(f"invalid chunk: {chunk_index}/{chunk_count}")
    parts = partition_jp_refresh_tasks(tasks, chunk_count)
    if chunk_index > len(parts):
        return []
    return parts[chunk_index - 1]
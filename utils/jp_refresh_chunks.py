"""JP refresh タスクの subprocess 分割（重量源の分散）。"""

from __future__ import annotations

_JP_HEAVY_SINGLE_KEYS = frozenset({"rakuten", "hatena", "note", "kkj"})
_JP_HEAVY_MULTI_KEYS = frozenset({"openalex", "book", "twitch"})


def partition_jp_refresh_tasks(tasks: list, chunk_count: int) -> list[list]:
    """JP タスクを chunk_count 個の subprocess 用バケットへ分散。"""
    if chunk_count <= 1:
        return [tasks]
    buckets: list[list] = [[] for _ in range(chunk_count)]
    singles: list = []
    multis: dict[str, list] = {}
    rest: list = []
    for task in tasks:
        key = task[0]
        if key in _JP_HEAVY_SINGLE_KEYS:
            singles.append(task)
        elif key in _JP_HEAVY_MULTI_KEYS:
            multis.setdefault(key, []).append(task)
        else:
            rest.append(task)
    idx = 0
    for task in singles:
        buckets[idx % chunk_count].append(task)
        idx += 1
    for key in ("openalex", "book", "twitch"):
        for task in multis.get(key, []):
            buckets[idx % chunk_count].append(task)
            idx += 1
    for task in rest:
        buckets[idx % chunk_count].append(task)
        idx += 1
    return [b for b in buckets if b]


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

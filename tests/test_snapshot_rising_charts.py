"""Tests for rank chart helpers in scripts/snapshot_rising.py."""

import importlib.util
import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "snapshot_rising.py"


@pytest.fixture(scope="module")
def sr():
    spec = importlib.util.spec_from_file_location("snapshot_rising", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_format_rank_svg_chart_places_better_rank_higher(sr):
    chart = sr.format_rank_svg_chart(
        "League of Legends",
        "日別ベスト順位（上ほど上位）",
        ["06-24", "06-26", "06-27"],
        [2, 1, 1],
    )
    assert chart.startswith("<svg ")
    y_by_rank = {
        int(m.group(2)): float(m.group(1))
        for m in re.finditer(r'<text [^>]*y="([\d.]+)"[^>]*>(\d+)位</text>', chart)
    }
    assert y_by_rank[1] < y_by_rank[2]


def test_format_rank_svg_chart_skips_flat_ranks(sr):
    assert sr.format_rank_svg_chart("Flat", "sub", ["a", "b"], [4, 4]) == ""


def test_rank_chart_coordinates_top_is_better_rank(sr):
    _, ys, _, _, _, _ = sr.rank_chart_coordinates([8, 2])
    assert ys[1] < ys[0]

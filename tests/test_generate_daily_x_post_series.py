"""Tests for scripts/generate_daily_x_post_series.py."""

import importlib.util
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_daily_x_post_series.py"


@pytest.fixture(scope="module")
def gx():
    spec = importlib.util.spec_from_file_location("generate_daily_x_post_series", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_resp(payload: dict):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = payload
    return r


def _jp_payloads():
    return [
        {"data": [{"keyword": "g1"}, {"keyword": "g2"}]},
        {"data": [{"title": "yt"}]},
        {"data": [{"title": "nh"}]},
        {"data": [{"title": "wn"}]},
        {"data": [{"title": "z"}]},
        {"data": [{"title": "jp"}]},
        {"data": [{"title": "mu"}]},
        {"data": [{"title": "mv"}]},
    ]


def _us_payloads():
    return [
        {"data": [{"keyword": "ug1"}, {"keyword": "ug2"}]},
        {"data": [{"title": "uyt"}]},
        {"data": [{"title": "cnn"}]},
        {"data": [{"cve_id": "CVE-1"}]},
        {"data": [{"title": "dev"}]},
        {"data": [{"title": "thn"}]},
        {"data": [{"title": "umu"}]},
        {"data": [{"title": "umv"}]},
    ]


def _triple_flat(series: dict) -> dict:
    return {"07": dict(series), "13": dict(series), "19": dict(series)}


@pytest.mark.parametrize("force_refresh,needle", [(True, "force_refresh=true"), (False, "force_refresh=false")])
def test_build_jp_block_request_urls_include_force_refresh_flag(gx, monkeypatch, force_refresh, needle):
    payloads = _jp_payloads()
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _mk_resp(payloads[len(calls) - 1])

    monkeypatch.setattr(gx.requests, "get", fake_get)
    gx.build_jp_block("https://example.com", "2026-05-12", force_refresh=force_refresh)
    assert len(calls) == 8
    for u in calls:
        assert needle in u


@pytest.mark.parametrize("force_refresh,needle", [(True, "force_refresh=true"), (False, "force_refresh=false")])
def test_build_us_block_request_urls_include_force_refresh_flag(gx, monkeypatch, force_refresh, needle):
    payloads = _us_payloads()
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _mk_resp(payloads[len(calls) - 1])

    monkeypatch.setattr(gx.requests, "get", fake_get)
    gx.build_us_block("https://example.com", "2026-05-12", force_refresh=force_refresh)
    assert len(calls) == 8
    for u in calls:
        assert needle in u


def test_google_line_snapshot_pair_and_single(gx):
    pair = [{"t": "A"}, {"t": "B"}]
    assert gx._google_line_snapshot(pair, sep="／") == "A／B"
    single = [{"t": "Only"}]
    assert gx._google_line_snapshot(single, sep=" / ") == "Only"


def test_build_blocks_from_snapshots_match_expected_lines(gx):
    flat = {
        "google_trends_jp": [{"t": "g1"}, {"t": "g2"}],
        "youtube_trends_jp": [{"t": "yt"}],
        "nhk_jp": [{"t": "nh"}],
        "worldnews_jp": [{"t": "wn"}],
        "zenn_jp": [{"t": "z"}],
        "jpcert_jp": [{"t": "Weekly Report: WRX"}],
        "music_trends_jp": [{"t": "mu"}],
        "movie_jp": [{"t": "mv"}],
        "google_trends_us": [{"t": "ug1"}, {"t": "ug2"}],
        "youtube_trends_us": [{"t": "uyt"}],
        "cnn_us": [{"t": "cnn"}],
        "cisa_kev_us": [{"t": "CVE-2026-1"}],
        "devto_us": [{"t": "dev"}],
        "thehackernews_us": [{"t": "thn"}],
        "music_trends_us": [{"t": "umu"}],
        "movie_us": [{"t": "umv"}],
    }
    bundle = _triple_flat(flat)
    jp = gx.build_jp_block_from_snapshots(bundle, "2026-05-12", max_jp_x_weighted=0)
    assert "g1／g2" in jp
    assert "nh／wn" in jp
    assert "z／WR WRX" in jp
    us = gx.build_us_block_from_snapshots(bundle, "2026-05-12", max_chars=0)
    assert "ug1 / ug2" in us
    assert "CVE-2026-1" in us


def test_pick_prefers_label_in_more_slots(gx):
    """3スロットに同じラベルがあるほどスコアが上がり、Google の②語目に選ばれやすい。"""
    bundle = {
        "07": {"google_trends_jp": [{"t": "RareSecond", "r": 2}, {"t": "AlwaysTop", "r": 1}]},
        "13": {"google_trends_jp": [{"t": "AlwaysTop", "r": 1}]},
        "19": {"google_trends_jp": [{"t": "AlwaysTop", "r": 1}]},
    }
    line = gx.google_line_from_slots(bundle, "google_trends_jp", sep="／")
    assert "AlwaysTop" in line
    assert line.startswith("AlwaysTop")


def test_pick_prefers_rank_jump_when_freq_equal(gx):
    bundle = {
        "07": {"google_trends_jp": [{"t": "Climber", "r": 20}, {"t": "Flat", "r": 2}]},
        "13": {"google_trends_jp": [{"t": "Climber", "r": 12}, {"t": "Flat", "r": 2}]},
        "19": {"google_trends_jp": [{"t": "Climber", "r": 3}, {"t": "Flat", "r": 2}]},
    }
    top = gx.pick_top_labels(bundle, "google_trends_jp", count=2)
    assert top[0] == "Climber"


def test_load_snapshots_daytime_slots_from_api_parses_payload(gx, monkeypatch):
    api_rows = [
        {"slot": "07", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]},
        {"slot": "01", "series_key": "google_trends_jp", "items": [{"t": "ignore", "r": 1}]},
        {"slot": "19", "series_key": "google_trends_jp", "items": [{"t": "b", "r": 1}]},
    ]

    def fake_get(url, **_kwargs):
        assert "daily-snapshots" in url
        assert "business_day=2026-05-12" in url
        return _mk_resp({"success": True, "data": api_rows})

    monkeypatch.setattr(gx.requests, "get", fake_get)
    out = gx.load_snapshots_daytime_slots_from_api("https://example.com", date(2026, 5, 12))
    assert out["07"]["google_trends_jp"][0]["t"] == "a"
    assert out["19"]["google_trends_jp"][0]["t"] == "b"
    assert "01" not in out


def test_load_snapshots_daytime_slots_from_api_empty_raises(gx, monkeypatch):
    def fake_get(url, **_kwargs):
        return _mk_resp({"success": True, "data": []})

    monkeypatch.setattr(gx.requests, "get", fake_get)
    with pytest.raises(ValueError, match="No trend_daily_snapshots"):
        gx.load_snapshots_daytime_slots_from_api("https://example.com", date(2026, 5, 12))


def test_load_snapshots_daytime_merges_slots(gx, monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            pass

        def fetchall(self):
            return [
                {
                    "slot": "07",
                    "series_key": "google_trends_jp",
                    "items": [{"t": "morning", "r": 1}],
                },
                {
                    "slot": "19",
                    "series_key": "google_trends_jp",
                    "items": [{"t": "eve", "r": 1}],
                },
            ]

    class FakeConn:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(gx.psycopg2, "connect", lambda url, connect_timeout=15: FakeConn())
    out = gx.load_snapshots_daytime_slots("postgresql://test/db", date(2026, 5, 12))
    assert out["07"]["google_trends_jp"][0]["t"] == "morning"
    assert out["19"]["google_trends_jp"][0]["t"] == "eve"

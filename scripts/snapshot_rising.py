"""
07 / 13 / 19 スナップショット横断の「急上昇」選定ロジック。

``generate_ai_daily_summary`` が本番で利用（日次サマリーの急上昇3つ等）。
``generate_daily_x_post_series`` も同じ判断軸を **共有していたが、X 投稿系列は 2026-07 運用停止**。
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

DAYTIME_SLOTS = ("07", "13", "19")

WEAK_RISING_LABEL = re.compile(
    r"^(pickup|official|news|video|動画|ニュース|…+)$",
    re.I,
)
NOISY_PROCUREMENT = re.compile(
    r"(LICENSE\s+RENEWAL|POP:\s*\d|INFINIBAND|FIBRE\s+OPTIC|usaspending|調達|契約番号)",
    re.I,
)


def snapshot_top_n() -> int:
    try:
        return max(1, min(25, int(os.getenv("TREND_SNAPSHOT_TOP_N", "10"))))
    except (TypeError, ValueError):
        return 10


def rank_out_of_range() -> int:
    return snapshot_top_n() + 1


def normalize_label_key(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).strip()).lower()[:600]


def clean_rising_display(display: str) -> str:
    s = re.sub(r"^【[^】]{1,16}】\s*", "", str(display).strip())
    return re.sub(r"\s+", " ", s).strip()


# 先頭欠落タイトル（例: 「リポジトリに参加した…」が「に参加した…」だけ残る）
_FRAGMENT_LABEL_RE = re.compile(
    r"^(に|を|が|は|と|で|へ|も|や|から|まで|より)"
    r"(参加|出演|登場|関連|関する|における|について|対応|発表|公開|更新|配信|発売)"
)


def is_fragment_label(display: str) -> bool:
    s = clean_rising_display(display)
    if not s:
        return True
    return bool(_FRAGMENT_LABEL_RE.search(s))


def is_weak_rising_label(display: str) -> bool:
    s = clean_rising_display(display)
    if not s or s == "…" or len(s) < 4:
        return True
    return bool(WEAK_RISING_LABEL.match(s))


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text)


def series_pref_score(series_key: str) -> int:
    sk = (series_key or "").lower()
    if sk.endswith("_jp") or "_jp_" in sk:
        return 3
    if sk.endswith("_us") or "_us_" in sk:
        return 0
    return 1


def is_noisy_label(display: str, series_key: str = "") -> bool:
    """調達行・英語長文など、一般読者向けから除外するラベル。"""
    if is_weak_rising_label(display):
        return True
    s = clean_rising_display(display)
    if is_fragment_label(s):
        return True
    sk = (series_key or "").lower()
    if len(s) > 100:
        return True
    if NOISY_PROCUREMENT.search(s):
        return True
    if any(p in sk for p in ("usaspending_", "kkj_", "estat_", "bls_")) and len(s) > 45:
        return True
    if _ascii_ratio(s) > 0.88 and len(s) > 50 and series_pref_score(series_key) < 2:
        return True
    return False


def rank_jump_score(ranks: dict[str, int]) -> float:
    """07→13→19 の隣接差分合計（上昇は加点、下落は減点）。未掲載スロットは圏外順位。"""
    oor = rank_out_of_range()
    prev_eff: Optional[int] = None
    s = 0.0
    for slot in DAYTIME_SLOTS:
        cur = int(ranks[slot]) if slot in ranks else oor
        if prev_eff is not None:
            s += float(prev_eff - cur)
        prev_eff = cur
    return s


def rising_qualifies(ranks: dict[str, int], jump: float) -> bool:
    """正の net jump、2スロット以上掲載、実観測で終わりだけ悪化は除外。"""
    if jump <= 0:
        return False
    observed = [(s, int(ranks[s])) for s in DAYTIME_SLOTS if s in ranks]
    if len(observed) < 2:
        return False
    if observed[-1][1] > observed[0][1]:
        return False
    return True


def daytime_best_rank(ranks: dict[str, int]) -> int:
    vals = [int(ranks[s]) for s in DAYTIME_SLOTS if s in ranks]
    return min(vals) if vals else 999


def format_rank_trend_markdown(
    x_axis_labels: list[str],
    rank_vals: list[int],
) -> str:
    """順位推移の一行（日次向け・Y 軸なし・全 Markdown ビューア対応）。

    日次はスロットが少ないためテキストで十分。週次は Mermaid + テキスト一行。
    """
    if len(rank_vals) < 2 or len(set(rank_vals)) < 2:
        return ""
    if len(x_axis_labels) != len(rank_vals):
        return ""
    trend = " → ".join(x_axis_labels)
    if rank_vals[-1] < rank_vals[0]:
        arrow = " ↑"
    elif rank_vals[-1] > rank_vals[0]:
        arrow = " ↓"
    else:
        arrow = ""
    return f"> **順位の動き**（上ほど良い）: {trend}{arrow}"


def mermaid_rank_y_axis_high(rank_vals: list[int]) -> int:
    """表示用 Y 上限（実順位の最大+1）。"""
    if not rank_vals:
        return 3
    r_max = max(rank_vals)
    r_min = min(rank_vals)
    y_high = r_max + 1
    if y_high - r_min < 2:
        y_high = r_min + 2
    return max(y_high, 3)


def mermaid_rank_plot_value(rank: int, y_high: int) -> int:
    """実順位をプロット値へ（大きいほど上＝上位）。"""
    return y_high + 1 - int(rank)


def _svg_escape(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def rank_chart_coordinates(
    rank_vals: list[int],
    *,
    width: int = 560,
    height: int = 200,
) -> tuple[list[float], list[float], int, int, int, int]:
    """順位列から描画座標（上＝数字小＝上位、Y 軸目盛なし）。"""
    plot_left, plot_right = 24, width - 16
    plot_top, plot_bottom = 36, 148
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top
    r_min = min(rank_vals)
    r_max = max(rank_vals)
    span = max(r_max - r_min, 1)
    n = len(rank_vals)
    xs = [
        plot_left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
        for i in range(n)
    ]
    ys = [plot_top + (r - r_min) / span * plot_h for r in rank_vals]
    return xs, ys, plot_left, plot_right, plot_top, plot_bottom


def format_rank_svg_chart(
    safe_title: str,
    subtitle: str,
    x_axis_labels: list[str],
    rank_vals: list[int],
) -> str:
    """順位推移の SVG 折れ線（週次向け・上ほど上位・Y 軸目盛なし）。

    Mermaid xychart は多くの Markdown プレビューで Y 軸 config が効かないため SVG を使う。
    """
    if len(rank_vals) < 2 or len(set(rank_vals)) < 2:
        return ""
    if len(x_axis_labels) != len(rank_vals):
        return ""
    width, height = 560, 200
    xs, ys, _, _, _, plot_bottom = rank_chart_coordinates(
        rank_vals, width=width, height=height
    )
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    stroke = "#0d9488"
    title = _svg_escape(f"{safe_title} — {subtitle}")
    parts = [
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 560 200\" role=\"img\" "
        f"aria-label=\"{title}\">",
        f"<title>{title}</title>",
        f"<text x=\"{width / 2:.1f}\" y=\"18\" text-anchor=\"middle\" font-size=\"12\" "
        f"font-family=\"system-ui,sans-serif\" fill=\"#334155\">{title}</text>",
        f"<polyline fill=\"none\" stroke=\"{stroke}\" stroke-width=\"2.5\" points=\"{points}\"/>",
    ]
    for x, y, rank, x_label in zip(xs, ys, rank_vals, x_axis_labels):
        parts.append(
            f"<circle cx=\"{x:.1f}\" cy=\"{y:.1f}\" r=\"4.5\" fill=\"#fff\" stroke=\"{stroke}\" stroke-width=\"2\"/>"
        )
        parts.append(
            f"<text x=\"{x:.1f}\" y=\"{y - 10:.1f}\" text-anchor=\"middle\" font-size=\"11\" "
            f"font-family=\"system-ui,sans-serif\" fill=\"{stroke}\">{int(rank)}位</text>"
        )
        parts.append(
            f"<text x=\"{x:.1f}\" y=\"{plot_bottom + 18:.1f}\" text-anchor=\"middle\" font-size=\"10\" "
            f"font-family=\"system-ui,sans-serif\" fill=\"#64748b\">{_svg_escape(x_label)}</text>"
        )
    parts.append("</svg>")
    return "\n".join(parts)


def format_rank_mermaid_xychart(
    safe_title: str,
    subtitle: str,
    x_axis_labels: list[str],
    rank_vals: list[int],
) -> str:
    """順位推移の Mermaid 折れ線（週次・Cursor 等のプレビュー向け）。

    プロット値は ``y_high + 1 - 順位`` で反転（2位が上、8位が下）。各点ラベルは実順位「N位」。
    Cursor プレビューでは ``yAxis.showLabel: false`` が効かず左目盛が出ることがある。
    その場合は各点ラベルと直下のテキスト一行（日次と同形式）を参照。
    """
    if len(rank_vals) < 2 or len(set(rank_vals)) < 2:
        return ""
    if len(x_axis_labels) != len(rank_vals):
        return ""
    labels = ", ".join(f'"{lb}"' for lb in x_axis_labels)
    y_high = mermaid_rank_y_axis_high(rank_vals)
    line_parts = [
        f'{mermaid_rank_plot_value(int(r), y_high)} "{int(r)}位"' for r in rank_vals
    ]
    line_str = ", ".join(line_parts)
    return (
        "```mermaid\n"
        "---\n"
        "config:\n"
        "  xyChart:\n"
        "    showLegend: false\n"
        "    yAxis:\n"
        "      showLabel: false\n"
        "      showTitle: false\n"
        "      showTick: false\n"
        "      showAxisLine: false\n"
        "  themeVariables:\n"
        "    xyChart:\n"
        "      yAxisLabelColor: transparent\n"
        "      yAxisTitleColor: transparent\n"
        "      yAxisTickColor: transparent\n"
        "      yAxisLineColor: transparent\n"
        "---\n"
        "xychart\n"
        f'    title "{safe_title} — {subtitle}"\n'
        f"    x-axis [{labels}]\n"
        f"    line [{line_str}]\n"
        "```"
    )


def pick_display_from_agg(agg: dict[str, Any]) -> str:
    """表示ラベルは非断片・長い表記を優先し、同点なら最良順位のスロットを使う。"""
    ranks = agg.get("ranks") or {}
    by_slot = agg.get("display_by_slot") or {}
    candidates: list[tuple[int, int, int, str]] = []
    for slot in DAYTIME_SLOTS:
        d = by_slot.get(slot)
        if not d:
            continue
        cleaned = clean_rising_display(str(d))
        if not cleaned:
            continue
        r = ranks.get(slot)
        rank_prio = int(r) if r is not None else 999
        frag_penalty = 1 if is_fragment_label(cleaned) else 0
        candidates.append((frag_penalty, -len(cleaned), rank_prio, cleaned))
    if not candidates:
        return ""
    candidates.sort()
    return candidates[0][3]


def aggregate_labels_for_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for slot in DAYTIME_SLOTS:
        items = (series_by_slot.get(slot) or {}).get(series_key) or []
        for it in items:
            if not isinstance(it, dict):
                continue
            raw_t = it.get("t")
            if raw_t is None or not str(raw_t).strip():
                continue
            display = str(raw_t).strip()
            nk = normalize_label_key(display)
            try:
                r = int(it.get("r"))
            except (TypeError, ValueError):
                r = 999
            agg = out.get(nk)
            if agg is None:
                agg = {"display_by_slot": {}, "ranks": {}, "series_key": series_key}
                out[nk] = agg
            agg["display_by_slot"][slot] = display
            prev = agg["ranks"].get(slot)
            if prev is None or r < prev:
                agg["ranks"][slot] = r
    return out


def collect_rising_candidates(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_keys: tuple[str, ...] | list[str],
    *,
    display_postprocess: Callable[[str, str], str] | None = None,
    tail_for_series: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """全 series 横断。ラベルキーごとに最良候補を1つ。資格・ノイズ済み。"""
    best: dict[str, dict[str, Any]] = {}
    for series_key in series_keys:
        aggs = aggregate_labels_for_series(series_by_slot, series_key)
        tail = (tail_for_series(series_key) if tail_for_series else "")
        for nk, agg in aggs.items():
            ranks = agg.get("ranks") or {}
            jump = rank_jump_score(ranks)
            raw_display = pick_display_from_agg(agg)
            if display_postprocess:
                raw_display = display_postprocess(series_key, raw_display)
            display = clean_rising_display(raw_display)
            if not display or not rising_qualifies(ranks, jump) or is_noisy_label(
                display, series_key
            ):
                continue
            freq = len(set(ranks.keys()) & set(DAYTIME_SLOTS))
            r_best = daytime_best_rank(ranks)
            cand = {
                "nk": nk,
                "display": display,
                "tail": tail,
                "jump": jump,
                "freq": freq,
                "r_best": r_best,
                "series_key": series_key,
                "ranks": dict(ranks),
            }
            prev = best.get(nk)
            if prev is None or (cand["jump"], cand["freq"], -cand["r_best"]) > (
                prev["jump"],
                prev["freq"],
                -prev["r_best"],
            ):
                best[nk] = cand
    return list(best.values())


def pick_top_rising(
    candidates: list[dict[str, Any]],
    *,
    count: int,
) -> list[dict[str, Any]]:
    """jump 降順で最大 count 件（同軸は AI サマリーと同じ）。"""
    items = sorted(
        candidates,
        key=lambda c: (-c["jump"], -c["freq"], c["r_best"], c["display"]),
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in items:
        nk = c.get("nk") or ""
        if nk in seen:
            continue
        seen.add(nk)
        out.append(c)
        if len(out) >= count:
            break
    return out


_SLOTS_URL_ORDER = ("19", "13", "07", "01")


def url_from_thin_item(item: dict[str, Any]) -> Optional[str]:
    u = item.get("u")
    if u is None:
        return None
    s = str(u).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return None


def normalize_article_url(url: str) -> Optional[str]:
    """記事同一性の比較用。Google 検索 URL など記事を指さないものは None。"""
    s = str(url or "").strip()
    if not s.startswith(("http://", "https://")):
        return None
    try:
        p = urlparse(s)
    except ValueError:
        return None
    host = (p.hostname or "").lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "/").rstrip("/") or "/"
    if host == "google.com" and path == "/search":
        return None
    if host in ("youtu.be",):
        vid = path.lstrip("/").split("/")[0]
        return f"youtube:{vid}" if vid else None
    if host in ("youtube.com", "m.youtube.com"):
        vid = (parse_qs(p.query).get("v") or [None])[0]
        return f"youtube:{vid}" if vid else None
    return f"{host}{path}".lower()


def url_for_label_in_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    label: str,
) -> Optional[str]:
    """系列内でラベルに対応する記事 URL（19→13→07→01 の順）。"""
    nk = normalize_label_key(label)
    for slot in _SLOTS_URL_ORDER:
        for it in (series_by_slot.get(slot) or {}).get(series_key) or []:
            if not isinstance(it, dict):
                continue
            if normalize_label_key(str(it.get("t") or "")) == nk:
                u = url_from_thin_item(it)
                if u:
                    return u
    return None


_FALLBACK_SEARCH_Q_MAX = 48


def fallback_search_url(label: str) -> str:
    """記事 URL が無いときの Google 検索。長タイトルは q を短縮する。"""
    query = clean_rising_display(label)
    if len(query) > _FALLBACK_SEARCH_Q_MAX:
        cut = query[:_FALLBACK_SEARCH_Q_MAX].rstrip()
        for sep in ("！", "!", "。", " ", "　", "・", "｜", "|", "【"):
            idx = cut.rfind(sep)
            if idx >= max(12, _FALLBACK_SEARCH_Q_MAX // 3):
                cut = cut[:idx].rstrip()
                break
        query = cut
    return f"https://www.google.com/search?q={quote_plus(query)}"


def article_url_for_rising(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    display: str,
) -> str:
    """急上昇表示用 URL。スナップに u が無ければ Google 検索。"""
    return url_for_label_in_series(series_by_slot, series_key, display) or fallback_search_url(
        display
    )

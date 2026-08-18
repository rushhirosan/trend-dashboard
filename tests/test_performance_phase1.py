"""Phase1 パフォーマンス変更のテンプレート回帰テスト"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def _head_section(html: str) -> str:
    return html.split("</head>", 1)[0]


def _blocking_external_scripts(head_html: str) -> list[str]:
    """head 内の同期外部 script（async/defer/ld+json 以外）"""
    found = []
    for match in re.finditer(r"<script\b[^>]*>", head_html, flags=re.IGNORECASE):
        tag = match.group(0)
        if 'type="application/ld+json"' in tag:
            continue
        if 'src=' not in tag:
            continue
        if "async" in tag or "defer" in tag:
            continue
        found.append(tag)
    return found


def test_index_head_has_no_blocking_scripts():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    blocking = _blocking_external_scripts(_head_section(html))
    assert blocking == [], f"blocking scripts in head: {blocking}"


def test_us_trends_head_has_no_blocking_scripts():
    html = (TEMPLATES / "us_trends.html").read_text(encoding="utf-8")
    blocking = _blocking_external_scripts(_head_section(html))
    assert blocking == [], f"blocking scripts in head: {blocking}"


def test_index_deferred_scripts_at_body_end():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    tail = html.rsplit("</body>", 1)[0]
    sync_pos = tail.rfind("dashboard_summary_height_sync.html")
    defer_pos = tail.rfind('defer src="{{ url_for(\'static\', filename=\'js/app.js\')')
    assert sync_pos != -1 and defer_pos != -1
    assert sync_pos < defer_pos


def test_index_removed_page_specific_css():
    head = _head_section((TEMPLATES / "index.html").read_text(encoding="utf-8"))
    assert "data-status.css" not in head
    assert "subscription.css" not in head


def test_data_status_and_subscription_keep_own_css():
    ds = (TEMPLATES / "data-status.html").read_text(encoding="utf-8")
    sub = (TEMPLATES / "subscription.html").read_text(encoding="utf-8")
    assert "data-status.css" in ds
    assert "subscription.css" in sub


def test_vendor_assets_self_hosted():
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "partials/vendor_assets.html" in index
    assert "cdnjs.cloudflare.com/ajax/libs/bootstrap" not in index
    assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" not in index
    assert "vendor/bootstrap/5.1.3/bootstrap.bundle.min.js" in index


def test_fontawesome_subset_exists():
    css = (ROOT / "static" / "css" / "fontawesome-subset.css").read_text(encoding="utf-8")
    assert "fa-chart-line" in css
    assert ".fa-solid,.fas{font-family:" in css
    assert ".fa-brands,.fab{font-family:" in css
    assert ".ttf" not in css
    assert "font-display:swap" in css
    assert "v4compatibility" not in css
    assert len(css) < 50_000


def test_noto_sans_jp_self_hosted():
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    head = _head_section(index)
    assert "partials/jp_web_font.html" in index
    assert "fonts.googleapis.com" not in head
    assert "fonts.gstatic.com" not in head
    css = (ROOT / "static" / "css" / "noto-sans-jp.css").read_text(encoding="utf-8")
    assert "Noto Sans JP" in css
    assert "font-display: optional" in css
    font = ROOT / "static" / "vendor" / "noto-sans-jp" / "japanese-400-normal.woff2"
    assert font.is_file()
    assert font.stat().st_size > 100_000


def test_inter_self_hosted():
    us = (TEMPLATES / "us_trends.html").read_text(encoding="utf-8")
    head = _head_section(us)
    assert "partials/us_web_font.html" in us
    assert "fonts.googleapis.com" not in head
    assert "fonts.gstatic.com" not in head
    css = (ROOT / "static" / "css" / "inter.css").read_text(encoding="utf-8")
    assert "Inter" in css
    assert "font-display: swap" in css
    font = ROOT / "static" / "vendor" / "inter" / "latin-400-normal.woff2"
    assert font.is_file()
    assert font.stat().st_size > 10_000


def test_jp_lazy_load_has_ssr_skip():
    dm = (ROOT / "static" / "js" / "data-management.js").read_text(encoding="utf-8")
    assert "loadNewsBundleUnlessSsr" in dm
    assert "loadForTab" in dm
    assert "tbodyHasTrendDataRows" in (ROOT / "static" / "js" / "app-common.js").read_text(encoding="utf-8")


def test_index_async_non_critical_stylesheets():
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    vendor = (TEMPLATES / "partials" / "vendor_assets.html").read_text(encoding="utf-8")
    async_css = (TEMPLATES / "partials" / "async_stylesheet.html").read_text(encoding="utf-8")
    assert "async_stylesheet.html" in index
    assert "async_stylesheet.html" in vendor
    assert 'filename=\'css/trends.css\') }}" rel="stylesheet"' not in index
    assert "fontawesome-subset.css" in vendor
    assert "onload=" in async_css


def test_jp_noto_preload_fetchpriority():
    jp_font = (TEMPLATES / "partials" / "jp_web_font.html").read_text(encoding="utf-8")
    assert "fetchpriority" in jp_font
    assert "noto-optional" in jp_font or "20260627-noto-optional" in jp_font


def test_category_tabs_have_roving_tabindex_and_keyboard_helper():
    jp = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    us = (TEMPLATES / "us_trends.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app-common.js").read_text(encoding="utf-8")
    assert 'id="tab-all"' in jp and 'tabindex="0"' in jp
    assert 'id="tab-news"' in jp and 'tabindex="-1"' in jp
    assert 'id="tab-all"' in us and 'tabindex="0"' in us
    assert "setupTrendCategoryTabKeyboard" in js
    assert "ArrowRight" in js
    assert "ArrowLeft" in js

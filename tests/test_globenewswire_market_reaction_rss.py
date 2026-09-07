"""GlobeNewswire × Market Reaction: RSS timeout/retry と 0件原因の分岐。"""

from unittest.mock import MagicMock, patch

import requests

from services.trends.globenewswire_market_reaction_trends import (
    RSS_MAX_ATTEMPTS,
    GlobeNewswireMarketReactionTrendsManager,
    _to_yahoo_symbol,
)


def _manager():
    with patch.object(GlobeNewswireMarketReactionTrendsManager, "__init__", lambda self: None):
        m = GlobeNewswireMarketReactionTrendsManager()
    m.rss_url = "https://example.com/feed"
    m.session = MagicMock()
    m.rate_limiter = MagicMock()
    return m


def test_parse_feed_retries_on_timeout_then_succeeds():
    m = _manager()
    ok = MagicMock()
    ok.status_code = 200
    ok.content = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Acme Corp Update</title>
        <link href="https://example.com/1"/>
        <category term="NYSE:ACME"/>
      </entry>
    </feed>
    """
    m.session.get.side_effect = [
        requests.exceptions.Timeout("slow"),
        ok,
    ]

    items, reason = m._parse_feed()

    assert reason is None
    assert len(items) == 1
    assert items[0]["title"] == "Acme Corp Update"
    assert m.session.get.call_count == 2


def test_parse_feed_timeout_exhaustion_returns_reason():
    m = _manager()
    m.session.get.side_effect = requests.exceptions.Timeout("slow")

    items, reason = m._parse_feed()

    assert items == []
    assert reason is not None
    assert "タイムアウト" in reason
    assert m.session.get.call_count == RSS_MAX_ATTEMPTS


def test_parse_feed_http_error_returns_reason_after_retry():
    m = _manager()
    bad = MagicMock()
    bad.status_code = 503
    bad.content = b""
    m.session.get.return_value = bad

    items, reason = m._parse_feed()

    assert items == []
    assert "HTTP 503" in (reason or "")
    assert m.session.get.call_count == RSS_MAX_ATTEMPTS


def test_fetch_trends_empty_rss_sets_empty_reason():
    m = _manager()
    m._parse_feed = MagicMock(return_value=([], "RSS取得がタイムアウトしました。"))
    m._fetch_market_data_batch = MagicMock()

    result = m._fetch_trends(limit=5)

    assert result["success"] is True
    assert result["data"] == []
    assert "タイムアウト" in result["empty_reason"]
    assert result["message"] == result["empty_reason"]
    m._fetch_market_data_batch.assert_not_called()


def test_fetch_trends_no_tickers_sets_empty_reason():
    m = _manager()
    m._parse_feed = MagicMock(
        return_value=(
            [{"title": "No ticker here", "url": "https://example.com/x", "description": "", "tags": []}],
            None,
        )
    )
    m._fetch_market_data_batch = MagicMock()

    result = m._fetch_trends(limit=5)

    assert result["success"] is True
    assert result["data"] == []
    assert "ティッカー" in result["empty_reason"]
    m._fetch_market_data_batch.assert_not_called()


def test_to_yahoo_symbol_maps_us_and_europe():
    assert _to_yahoo_symbol("NYSE", "DLR") == "DLR"
    assert _to_yahoo_symbol("NASDAQ", "AAPL") == "AAPL"
    assert _to_yahoo_symbol("Paris", "ALD") == "ALD.PA"
    assert _to_yahoo_symbol("LSE", "RAT") == "RAT.L"
    assert _to_yahoo_symbol("TSX", "ADN") == "ADN.TO"
    assert _to_yahoo_symbol("UnknownEx", "ABC") is None


def test_extract_ticker_from_paris_stock_tag():
    m = _manager()
    item = {
        "title": "Share buyback programme",
        "description": "",
        "tags": [
            {
                "term": "Paris:ALD",
                "scheme": "https://www.globenewswire.com/rss/stock",
                "label": None,
            }
        ],
    }
    assert m._extract_ticker(item) == "ALD.PA"


def test_extract_ticker_from_nyse_stock_tag():
    m = _manager()
    item = {
        "title": "Digital Realty announcement",
        "description": "",
        "tags": [
            {
                "term": "NYSE:DLR",
                "scheme": "https://www.globenewswire.com/rss/stock",
                "label": None,
            }
        ],
    }
    assert m._extract_ticker(item) == "DLR"


def test_fetch_trends_extracts_paris_tickers():
    m = _manager()
    m._parse_feed = MagicMock(
        return_value=(
            [
                {
                    "title": "ALD buyback",
                    "url": "https://example.com/ald",
                    "description": "",
                    "tags": [
                        {
                            "term": "Paris:ALD",
                            "scheme": "https://www.globenewswire.com/rss/stock",
                            "label": None,
                        }
                    ],
                }
            ],
            None,
        )
    )
    m._fetch_market_data_batch = MagicMock(
        return_value={"ALD.PA": {"change_percent": 1.5, "volume_spike": 2.0}}
    )

    result = m._fetch_trends(limit=5)

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["ticker"] == "ALD.PA"
    m._fetch_market_data_batch.assert_called_once_with(["ALD.PA"])

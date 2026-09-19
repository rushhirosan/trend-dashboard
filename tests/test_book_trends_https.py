"""Book trends URL normalization tests."""

from services.trends.book_trends import BookTrendsManager


def test_normalize_https_url_upgrades_http():
    assert (
        BookTrendsManager._normalize_https_url(
            "http://books.google.com/books/content?id=abc"
        )
        == "https://books.google.com/books/content?id=abc"
    )


def test_normalize_https_url_leaves_https_and_empty():
    url = "https://books.google.com/books/content?id=abc"
    assert BookTrendsManager._normalize_https_url(url) == url
    assert BookTrendsManager._normalize_https_url("") == ""
    assert BookTrendsManager._normalize_https_url(None) == ""


def test_normalize_us_book_record_all_image_fields():
    mgr = BookTrendsManager()
    record = {
        "image_url": "http://books.google.com/a",
        "thumbnail": "http://books.google.com/b",
        "small_thumbnail": "http://books.google.com/c",
        "medium": "http://books.google.com/d",
        "large": "http://books.google.com/e",
        "image_links": {
            "thumbnail": "http://books.google.com/f",
            "smallThumbnail": "http://books.google.com/g",
        },
    }
    out = mgr._normalize_us_book_record(record)
    assert out["image_url"].startswith("https://")
    assert out["thumbnail"].startswith("https://")
    assert out["image_links"]["thumbnail"].startswith("https://")


def _mgr_with_affiliate(tag='trendsdashboa-22'):
    mgr = BookTrendsManager.__new__(BookTrendsManager)
    mgr.amazon_affiliate_id = tag
    return mgr


def test_isbn13_978_converts_to_isbn10_asin():
    mgr = _mgr_with_affiliate()
    assert mgr._isbn_to_amazon_asin('9784088851747') == '4088851749'
    assert mgr._isbn_to_amazon_asin('978-4-08-885174-7') == '4088851749'


def test_isbn10_passthrough():
    mgr = _mgr_with_affiliate()
    assert mgr._isbn_to_amazon_asin('4088851749') == '4088851749'


def test_isbn13_979_cannot_convert():
    mgr = _mgr_with_affiliate()
    assert mgr._isbn_to_amazon_asin('9791234567896') is None


def test_generate_amazon_link_jp_uses_isbn10_dp():
    mgr = _mgr_with_affiliate()
    url = mgr._generate_amazon_link('ジャンプ', '9784088851747', 'JP')
    assert url == 'https://www.amazon.co.jp/dp/4088851749?tag=trendsdashboa-22'


def test_generate_amazon_link_falls_back_to_title_search():
    mgr = _mgr_with_affiliate()
    url = mgr._generate_amazon_link('Some Title', '9791234567896', 'JP')
    assert '/s?k=' in url
    assert 'tag=trendsdashboa-22' in url
    assert '/dp/' not in url


def test_backfill_overwrites_stale_isbn13_dp_link():
    mgr = _mgr_with_affiliate()
    result = {
        'data': [{
            'title': 'ジャンプ',
            'isbn': '9784088851747',
            'amazon_link': 'https://www.amazon.co.jp/dp/9784088851747?tag=trendsdashboa-22',
        }]
    }
    out = mgr._backfill_amazon_links(result, 'JP')
    assert out['data'][0]['amazon_link'] == (
        'https://www.amazon.co.jp/dp/4088851749?tag=trendsdashboa-22'
    )

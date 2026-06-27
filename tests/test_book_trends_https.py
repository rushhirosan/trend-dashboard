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

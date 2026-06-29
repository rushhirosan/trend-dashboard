"""楽天トレンドマネージャーのユニットテスト"""

from unittest.mock import MagicMock, patch

import pytest

from services.trends.rakuten_trends import RakutenTrendsManager


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setenv('RAKUTEN_APP_ID', 'test-app-id')
    monkeypatch.setenv('RAKUTEN_ACCESS_KEY', 'test-access-key')
    m = RakutenTrendsManager()
    m.rate_limiter = MagicMock()
    m.rate_limiter.wait_if_needed = MagicMock()
    return m


def test_parse_rakuten_ranking_items_format_version_2(manager):
    items = [
        {
            'itemName': '商品A',
            'itemCode': 'shop:123',
            'itemPrice': 1000,
            'reviewCount': 10,
            'reviewAverage': 4.5,
            'rank': 1,
            'itemUrl': 'https://example.com/a',
            'shopName': 'ショップA',
            'genreId': '100',
            'mediumImageUrls': [{'imageUrl': 'https://img.example/a.jpg'}],
        },
        {
            'itemName': '商品B',
            'itemCode': 'shop:456',
            'itemPrice': 2000,
            'reviewCount': 5,
            'reviewAverage': 3.0,
            'rank': 2,
            'itemUrl': 'https://example.com/b',
            'shopName': 'ショップB',
            'genreId': '200',
            'mediumImageUrls': [{'imageUrl': 'https://img.example/b.jpg'}],
        },
    ]
    result = manager._parse_rakuten_ranking_items(items, limit=25)
    assert len(result) == 2
    assert result[0]['title'] == '商品A'
    assert result[0]['rank'] == 1
    assert result[0]['sales_rank'] == 1
    assert result[1]['rank'] == 2


@patch('services.trends.rakuten_trends.requests.get')
def test_get_rakuten_ranking_uses_new_endpoint(mock_get, manager):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'items': [
            {
                'itemName': 'ランキング商品',
                'itemCode': 'shop:999',
                'itemPrice': 500,
                'reviewCount': 1,
                'reviewAverage': 5.0,
                'rank': 1,
                'itemUrl': 'https://example.com/item',
                'shopName': 'テスト店',
                'genreId': '565162',
                'mediumImageUrls': [{'imageUrl': 'https://img.example/x.jpg'}],
            }
        ]
    }
    mock_get.return_value = mock_response

    result = manager._get_rakuten_ranking(genre_id='565162', limit=10)

    assert result['data']
    assert result['data'][0]['title'] == 'ランキング商品'
    called_url = mock_get.call_args[0][0]
    assert 'openapi.rakuten.co.jp/ichibaranking' in called_url
    called_params = mock_get.call_args[1]['params']
    assert called_params['applicationId'] == 'test-app-id'
    assert called_params['accessKey'] == 'test-access-key'
    assert called_params['genreId'] == '565162'


def test_credentials_required(monkeypatch):
    monkeypatch.delenv('RAKUTEN_ACCESS_KEY', raising=False)
    manager = RakutenTrendsManager()
    result = manager._get_rakuten_ranking()
    assert result['data'] == []
    assert 'RAKUTEN_ACCESS_KEY' in result['error']

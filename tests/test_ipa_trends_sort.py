# -*- coding: utf-8 -*-
"""IPA注意喚起のソートロジック（新規優先・更新は後）のユニットテスト"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trends.ipa_trends import IPATrendsManager


@pytest.fixture
def manager():
    return IPATrendsManager()


def _item(title, published_date, *, last_updated_date=None, is_updated=None):
    row = {
        'title': title,
        'published_date': published_date,
        'original_published_date': published_date,
    }
    if last_updated_date is not None:
        row['last_updated_date'] = last_updated_date
    if is_updated is not None:
        row['is_updated'] = is_updated
    return row


class TestIPAUpdateDetection:
    def test_detects_fullwidth_update_prefix(self, manager):
        assert manager._is_updated_alert('更新：Windows 10のサポート終了に伴う注意喚起') is True

    def test_detects_halfwidth_update_prefix(self, manager):
        assert manager._is_updated_alert('更新: テスト') is True

    def test_new_alert_is_not_update(self, manager):
        assert manager._is_updated_alert('「FileZen」における脆弱性について') is False


class TestIPASortItems:
    def test_new_alerts_rank_before_updates_on_same_day(self, manager):
        data = [
            _item(
                '更新：Windows 10のサポート終了に伴う注意喚起',
                '2026-06-01',
                last_updated_date='2026-06-01',
                is_updated=True,
            ),
            _item('「FileZen」におけるOSコマンドインジェクションの脆弱性について', '2026-06-01'),
            _item(
                '「LANSCOPE エンドポイントマネージャー オンプレミス版」におけるパストラバーサルの脆弱性について',
                '2026-06-01',
            ),
        ]
        sorted_data = manager._sort_ipa_items(data)
        titles = [x['title'] for x in sorted_data]
        assert titles[0].startswith('「FileZen」')
        assert titles[1].startswith('「LANSCOPE')
        assert titles[2].startswith('更新：Windows 10')

    def test_new_alerts_sorted_by_publication_date_desc(self, manager):
        data = [
            _item('Microsoft 製品の脆弱性対策について(2026年5月)', '2026-05-13'),
            _item('「FileZen」におけるOSコマンドインジェクションの脆弱性について', '2026-06-01'),
        ]
        sorted_data = manager._sort_ipa_items(data)
        assert sorted_data[0]['title'].startswith('「FileZen」')
        assert sorted_data[1]['title'].startswith('Microsoft')

    def test_updates_sorted_by_last_updated_date_desc(self, manager):
        data = [
            _item(
                '更新：古い更新記事',
                '2026-01-01',
                last_updated_date='2026-05-01',
                is_updated=True,
            ),
            _item(
                '更新：Windows 10のサポート終了に伴う注意喚起',
                '2024-10-01',
                last_updated_date='2026-06-01',
                is_updated=True,
            ),
        ]
        sorted_data = manager._sort_ipa_items(data)
        assert sorted_data[0]['title'].startswith('更新：Windows 10')
        assert sorted_data[1]['title'] == '更新：古い更新記事'

    def test_detects_update_from_title_when_is_updated_missing(self, manager):
        """キャッシュ読み出し時（is_updated 未保存）もタイトルで更新判定できる"""
        data = [
            _item('更新：Windows 10のサポート終了に伴う注意喚起', '2026-06-01', last_updated_date='2026-06-01'),
            _item('「FileZen」におけるOSコマンドインジェクションの脆弱性について', '2026-06-01'),
        ]
        sorted_data = manager._sort_ipa_items(data)
        assert sorted_data[0]['title'].startswith('「FileZen」')
        assert sorted_data[1]['title'].startswith('更新：Windows 10')

    def test_empty_list_returns_empty(self, manager):
        assert manager._sort_ipa_items([]) == []

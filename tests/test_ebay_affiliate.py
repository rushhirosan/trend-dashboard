#!/usr/bin/env python3
"""
eBayアフィリエイトURL生成のユニットテスト
"""

import os
import pytest


def test_ebay_add_affiliate_params_campid_and_mkrid():
    """campid と mkrid が正しくURLに付与されることを確認"""
    os.environ.pop('EBAY_CAMPAIGN_ID', None)
    os.environ.pop('EBAY_AFFILIATE_ID', None)
    os.environ.pop('EBAY_ROTATION_ID', None)

    os.environ['EBAY_CAMPAIGN_ID'] = '5339137875'
    os.environ['EBAY_ROTATION_ID'] = '711-53200-19255-0'

    try:
        from services.trends.ebay_trends import eBayTrendsManager
        mgr = eBayTrendsManager()
        result = mgr._add_affiliate_params('https://www.ebay.com/itm/123')
        assert 'campid=5339137875' in result
        assert 'mkrid=711-53200-19255-0' in result
        assert 'mkevt=1' in result
        assert 'mkcid=1' in result
        assert 'toolid=10001' in result
    finally:
        os.environ.pop('EBAY_CAMPAIGN_ID', None)
        os.environ.pop('EBAY_ROTATION_ID', None)


def test_ebay_add_affiliate_params_backward_compat_affiliate_id():
    """EBAY_AFFILIATE_ID のみ（10桁）で後方互換動作することを確認"""
    os.environ.pop('EBAY_CAMPAIGN_ID', None)
    os.environ.pop('EBAY_AFFILIATE_ID', None)
    os.environ.pop('EBAY_ROTATION_ID', None)

    os.environ['EBAY_AFFILIATE_ID'] = '5339137875'

    try:
        from services.trends.ebay_trends import eBayTrendsManager
        mgr = eBayTrendsManager()
        result = mgr._add_affiliate_params('https://www.ebay.com/itm/123')
        assert 'campid=5339137875' in result
        assert 'mkrid=711-53200-19255-0' in result  # default US
    finally:
        os.environ.pop('EBAY_AFFILIATE_ID', None)


def test_ebay_add_affiliate_params_no_campaign_returns_original():
    """campid 未設定時は元URLをそのまま返すことを確認"""
    os.environ.pop('EBAY_CAMPAIGN_ID', None)
    os.environ.pop('EBAY_AFFILIATE_ID', None)
    os.environ.pop('EBAY_ROTATION_ID', None)

    try:
        from services.trends.ebay_trends import eBayTrendsManager
        mgr = eBayTrendsManager()
        url = 'https://www.ebay.com/itm/123'
        result = mgr._add_affiliate_params(url)
        assert result == url
    finally:
        pass

#!/usr/bin/env python3
"""
トレンドダッシュボードの各ページをテストするスクリプト
"""

import requests
import sys
from datetime import datetime

BASE_URL = "https://trends-dashboard.fly.dev"
# ローカルテスト用
# BASE_URL = "http://localhost:5000"

def test_page(url, description):
    """ページの基本動作をテスト"""
    try:
        print(f"\n{'='*60}")
        print(f"テスト: {description}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        response = requests.get(url, timeout=10)
        
        # ステータスコードチェック
        if response.status_code == 200:
            print(f"✅ ステータスコード: {response.status_code}")
        else:
            print(f"❌ ステータスコード: {response.status_code}")
            return False
        
        # コンテンツサイズチェック
        content_length = len(response.content)
        if content_length > 1000:
            print(f"✅ コンテンツサイズ: {content_length:,} bytes")
        else:
            print(f"⚠️  コンテンツサイズが小さい: {content_length:,} bytes")
        
        # 重要なキーワードの存在チェック
        content = response.text.lower()
        checks = {
            'html': '<html' in content or '<!doctype' in content,
            'title': '<title' in content,
            'body': '<body' in content,
        }
        
        for key, found in checks.items():
            if found:
                print(f"✅ {key} タグが見つかりました")
            else:
                print(f"⚠️  {key} タグが見つかりませんでした")
        
        # エラーメッセージのチェック
        error_keywords = ['error', 'exception', 'traceback', '500', '404', 'not found']
        found_errors = [kw for kw in error_keywords if kw in content]
        if found_errors:
            print(f"⚠️  エラー関連のキーワードが見つかりました: {', '.join(found_errors)}")
        else:
            print(f"✅ エラー関連のキーワードは見つかりませんでした")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ タイムアウト: {url}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 接続エラー: {url}")
        return False
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

def test_api_endpoint(url, description):
    """APIエンドポイントをテスト"""
    try:
        print(f"\n{'='*60}")
        print(f"テスト: {description}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ ステータスコード: {response.status_code}")
            
            try:
                data = response.json()
                print(f"✅ JSON形式でレスポンスを取得")
                
                # 基本的な構造チェック
                if isinstance(data, dict):
                    print(f"✅ レスポンスは辞書形式")
                    if 'success' in data:
                        print(f"   成功フラグ: {data.get('success')}")
                    if 'data' in data:
                        data_count = len(data.get('data', [])) if isinstance(data.get('data'), list) else len(data.get('data', {}))
                        print(f"   データ件数: {data_count}")
                elif isinstance(data, list):
                    print(f"✅ レスポンスはリスト形式")
                    print(f"   データ件数: {len(data)}")
                    
            except ValueError:
                print(f"⚠️  JSON形式ではありません")
        else:
            print(f"❌ ステータスコード: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

def main():
    """メイン処理"""
    print(f"\n{'='*60}")
    print(f"トレンドダッシュボード テスト開始")
    print(f"テスト時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ベースURL: {BASE_URL}")
    print(f"{'='*60}")
    
    results = []
    
    # ページテスト
    pages = [
        ("/", "日本トレンドページ"),
        ("/us", "USトレンドページ"),
        ("/data-status", "データ鮮度情報ページ"),
        ("/subscription/", "サブスクリプションページ"),
    ]
    
    for path, description in pages:
        url = f"{BASE_URL}{path}"
        result = test_page(url, description)
        results.append(("ページ", description, result))
    
    # APIエンドポイントテスト
    api_endpoints = [
        ("/api/cache/data-freshness", "データ鮮度情報API"),
        ("/api/google-trends?region=JP", "Google Trends API (JP)"),
        ("/api/youtube-trends?region=JP", "YouTube Trends API (JP)"),
        ("/api/music-trends?service=spotify&region=JP", "Spotify Trends API (JP)"),
        ("/api/worldnews-trends?country=jp", "World News API (JP)"),
        ("/api/podcast-trends?trend_type=best_podcasts&region=jp", "Podcast Trends API (JP)"),
        ("/api/rakuten-trends", "楽天トレンドAPI"),
        ("/api/hatena-trends?category=all", "はてなブックマークAPI"),
        ("/api/twitch-trends?category=games", "Twitch Trends API"),
    ]
    
    for path, description in api_endpoints:
        url = f"{BASE_URL}{path}"
        result = test_api_endpoint(url, description)
        results.append(("API", description, result))
    
    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"テスト結果サマリー")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, _, result in results if result)
    total_count = len(results)
    
    for category, description, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status} - [{category}] {description}")
    
    print(f"\n{'='*60}")
    print(f"合計: {success_count}/{total_count} 成功")
    print(f"成功率: {success_count/total_count*100:.1f}%")
    print(f"{'='*60}\n")
    
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())


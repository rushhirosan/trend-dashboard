#!/usr/bin/env python3
"""
Google Trends API デバッグスクリプト
404エラーの原因を調査し、解決策を見つける
"""

import requests
from pytrends.request import TrendReq
import time
import json

def test_direct_google_trends():
    """Google Trendsに直接アクセスして状況を確認"""
    print("=== Google Trends 直接アクセステスト ===")
    
    # 1. Google Trendsのホームページにアクセス
    try:
        print("1. Google Trendsホームページにアクセス中...")
        response = requests.get('https://trends.google.com/trends/explore', 
                              headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
        print(f"   ステータスコード: {response.status_code}")
        print(f"   レスポンスサイズ: {len(response.text)} bytes")
        
        if response.status_code == 200:
            print("   ✅ ホームページアクセス成功")
        else:
            print(f"   ❌ ホームページアクセス失敗: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ エラー: {str(e)}")
    
    # 2. トレンド検索ページにアクセス
    try:
        print("\n2. トレンド検索ページにアクセス中...")
        response = requests.get('https://trends.google.com/trends/trendingsearches/daily', 
                              headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
        print(f"   ステータスコード: {response.status_code}")
        print(f"   レスポンスサイズ: {len(response.text)} bytes")
        
        if response.status_code == 200:
            print("   ✅ トレンド検索ページアクセス成功")
        else:
            print(f"   ❌ トレンド検索ページアクセス失敗: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ エラー: {str(e)}")

def test_pytrends_methods():
    """pytrendsの各メソッドをテスト"""
    print("\n=== pytrends メソッドテスト ===")
    
    # 異なる設定でテスト
    test_configs = [
        {'hl': 'en-US', 'tz': -300, 'desc': 'US English'},
        {'hl': 'ja-JP', 'tz': 540, 'desc': 'Japanese'},
        {'hl': 'en-GB', 'tz': 0, 'desc': 'UK English'}
    ]
    
    for config in test_configs:
        print(f"\n--- {config['desc']} でテスト ---")
        
        try:
            # より詳細な設定でTrendReqを初期化
            pytrends = TrendReq(
                hl=config['hl'],
                tz=config['tz'],
                timeout=(30, 60),
                retries=3,
                backoff_factor=0.3,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                }
            )
            
            print(f"   TrendReq初期化成功: hl={config['hl']}, tz={config['tz']}")
            
            # 各メソッドをテスト
            methods = [
                ('trending_searches', lambda: pytrends.trending_searches(pn='japan')),
                ('today_searches', lambda: pytrends.today_searches(pn='japan')),
                ('realtime_trending_searches', lambda: pytrends.realtime_trending_searches(pn='japan'))
            ]
            
            for method_name, method_func in methods:
                try:
                    print(f"   {method_name} を試行中...")
                    results = method_func()
                    
                    if results is not None and not results.empty:
                        print(f"   ✅ {method_name} 成功: {len(results)} 件のデータ")
                        print(f"      サンプル: {results.head(3).values.tolist()}")
                    else:
                        print(f"   ⚠️ {method_name} は空の結果を返しました")
                        
                except Exception as e:
                    print(f"   ❌ {method_name} 失敗: {str(e)}")
                    
                    # エラーの詳細を調査
                    if hasattr(e, 'response'):
                        print(f"      レスポンスステータス: {e.response.status_code}")
                        print(f"      レスポンスヘッダー: {dict(e.response.headers)}")
                        print(f"      レスポンス内容: {e.response.text[:200]}...")
                
                time.sleep(2)  # リクエスト間に遅延
                
        except Exception as e:
            print(f"   ❌ 設定 {config['desc']} でエラー: {str(e)}")

def test_alternative_approaches():
    """代替アプローチをテスト"""
    print("\n=== 代替アプローチテスト ===")
    
    try:
        print("1. 特定キーワードでのトレンド検索をテスト...")
        pytrends = TrendReq(hl='en-US', tz=-300)
        
        # 特定のキーワードでトレンドを取得
        pytrends.build_payload(['AI'], cat=0, timeframe='today 12-m', geo='', gprop='')
        df = pytrends.interest_over_time()
        
        if df is not None and not df.empty:
            print("   ✅ 特定キーワードでのトレンド取得成功")
            print(f"      データ形状: {df.shape}")
            print(f"      サンプルデータ: {df.head(3)}")
        else:
            print("   ❌ 特定キーワードでのトレンド取得失敗")
            
    except Exception as e:
        print(f"   ❌ 代替アプローチテスト失敗: {str(e)}")

def main():
    """メイン関数"""
    print("Google Trends API 404エラー調査開始")
    print("=" * 50)
    
    test_direct_google_trends()
    test_pytrends_methods()
    test_alternative_approaches()
    
    print("\n" + "=" * 50)
    print("調査完了")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
はてなブックマーク、Rakuten、Twitchのデータを既存のManagerクラスを使って取得・保存するスクリプト
"""

import os
from dotenv import load_dotenv
from hatena_trends import HatenaTrendsManager
from rakuten_trends import RakutenTrendsManager
from twitch_trends import TwitchTrendsManager

# 環境変数を読み込み
load_dotenv()

def fetch_hatena_data():
    """はてなブックマークのデータを取得・保存"""
    try:
        print("=== はてなブックマークデータ取得開始 ===")
        
        hatena_manager = HatenaTrendsManager()
        result = hatena_manager.get_hot_entries(category='all', limit=25)
        
        if result and 'data' in result and result['data']:
            print(f"✅ はてなブックマーク: {len(result['data'])}件のデータを取得しました")
            
            # 直接データベースに保存
            from database_config import TrendsCache
            cache = TrendsCache()
            category = "all"
            
            # 既存のデータを削除
            conn = cache.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM hatena_trends_cache WHERE category = %s", (category,))
            conn.commit()
            
            # 新しいデータを挿入
            for item in result['data']:
                cur.execute("""
                    INSERT INTO hatena_trends_cache 
                    (category, title, url, description, bookmark_count, rank, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    category, item.get('title', ''), item.get('url', ''), 
                    item.get('description', ''), item.get('bookmark_count', 0), 
                    item.get('rank', 0), item.get('created_at', None)
                ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print("✅ はてなブックマークデータをキャッシュに保存しました")
            return True
        else:
            print("❌ はてなブックマークデータの取得に失敗しました")
            return False
            
    except Exception as e:
        print(f"❌ はてなブックマークエラー: {e}")
        return False

def fetch_rakuten_data():
    """Rakutenのデータを取得・保存"""
    try:
        print("=== Rakutenデータ取得開始 ===")
        
        rakuten_manager = RakutenTrendsManager()
        result = rakuten_manager.get_popular_items(genre_id=None, limit=25)
        
        if result and 'data' in result and result['data']:
            print(f"✅ Rakuten: {len(result['data'])}件のデータを取得しました")
            
            # 直接データベースに保存
            from database_config import TrendsCache
            cache = TrendsCache()
            genre_id = "0"  # 総合
            
            # 既存のデータを削除
            conn = cache.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM rakuten_trends_cache WHERE genre_id = %s", (genre_id,))
            conn.commit()
            
            # 新しいデータを挿入
            for item in result['data']:
                cur.execute("""
                    INSERT INTO rakuten_trends_cache 
                    (genre_id, title, price, review_count, review_average, image_url, url, shop_name, rank, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    genre_id, item.get('title', ''), item.get('price', 0), 
                    item.get('review_count', 0), item.get('review_average', 0), 
                    item.get('image_url', ''), item.get('url', ''), 
                    item.get('shop_name', ''), item.get('rank', 0), 
                    item.get('created_at', None)
                ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print("✅ Rakutenデータをキャッシュに保存しました")
            return True
        else:
            print("❌ Rakutenデータの取得に失敗しました")
            return False
            
    except Exception as e:
        print(f"❌ Rakutenエラー: {e}")
        return False

def fetch_twitch_data():
    """Twitchのデータを取得・保存"""
    try:
        print("=== Twitchデータ取得開始 ===")
        
        twitch_manager = TwitchTrendsManager()
        result = twitch_manager.get_trends(limit=25)  # trend_typeパラメータを削除
        
        if result and 'data' in result and result['data']:
            print(f"✅ Twitch: {len(result['data'])}件のデータを取得しました")
            
            # 直接データベースに保存
            from database_config import TrendsCache
            cache = TrendsCache()
            trend_type = "games"
            
            # 既存のデータを削除
            conn = cache.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM twitch_trends_cache WHERE trend_type = %s", (trend_type,))
            conn.commit()
            
            # 新しいデータを挿入
            for item in result['data']:
                cur.execute("""
                    INSERT INTO twitch_trends_cache 
                    (trend_type, title, game_name, viewer_count, thumbnail_url, url, rank, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    trend_type, item.get('name', ''), item.get('name', ''), 
                    item.get('viewer_count', 0), item.get('box_art_url', ''), 
                    '', item.get('rank', 0), 
                    item.get('created_at', None)
                ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print("✅ Twitchデータをキャッシュに保存しました")
            return True
        else:
            print("❌ Twitchデータの取得に失敗しました")
            return False
            
    except Exception as e:
        print(f"❌ Twitchエラー: {e}")
        return False

def main():
    """メイン処理"""
    print("🚀 不足データの取得・保存開始")
    
    results = []
    
    # はてなブックマーク
    print("\n--- はてなブックマーク ---")
    results.append(("はてなブックマーク", fetch_hatena_data()))
    
    # Rakuten
    print("\n--- Rakuten ---")
    results.append(("Rakuten", fetch_rakuten_data()))
    
    # Twitch
    print("\n--- Twitch ---")
    results.append(("Twitch", fetch_twitch_data()))
    
    # 結果サマリー
    print("\n=== 結果サマリー ===")
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, success in results if success)
    print(f"\n成功: {success_count}/{len(results)}件")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
スケジューラーのメール自動送信機能をテストするスクリプト
対話式のため pytest ではスキップ。手動実行: python tests/test_scheduler_email.py
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

@pytest.mark.skip(reason="Interactive test with input(). Run manually: python tests/test_scheduler_email.py")
def test_scheduler_email():
    """スケジューラーのメール自動送信機能をテスト"""
    print("=" * 60)
    print("スケジューラーメール自動送信機能のテスト")
    print("=" * 60)
    
    # アプリケーションを作成
    app, scheduler = create_app()
    
    if not scheduler:
        print("❌ スケジューラーが初期化されていません")
        return False
    
    # SubscriptionManagerが初期化されているか確認
    if scheduler.subscription_manager is None:
        print("⚠️ SubscriptionManagerが初期化されていません")
        print("   メール自動送信はスキップされます")
        return False
    
    print("✅ スケジューラーとSubscriptionManagerが初期化されています")
    print()
    print("📧 スケジューラーを実行してメール自動送信をテストします...")
    print("   注意: 実際にメールが送信されます")
    print()
    
    # ユーザーに確認
    response = input("続行しますか？ (y/n): ")
    if response.lower() != 'y':
        print("テストをキャンセルしました")
        return False
    
    try:
        # スケジューラーの_fetch_all_trendsを実行
        # これにより、_save_trends_to_databaseが呼び出され、メール自動送信も実行される
        with app.app_context():
            scheduler._fetch_all_trends()
        
        print()
        print("✅ スケジューラー実行完了")
        print("📧 メール自動送信も実行されました（エラーがない場合）")
        print()
        print("💡 メールが送信されたか確認してください")
        
        return True
        
    except Exception as e:
        print(f"❌ スケジューラー実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_scheduler_email()
    sys.exit(0 if success else 1)



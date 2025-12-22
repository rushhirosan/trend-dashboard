#!/usr/bin/env python3
"""
UIテストスクリプト（Selenium使用）
ブラウザで実際にページを開いてUIの動作を確認します
"""

import sys
import time
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        USE_WEBDRIVER_MANAGER = True
    except ImportError:
        USE_WEBDRIVER_MANAGER = False
except ImportError:
    print("❌ Seleniumがインストールされていません")
    print("インストール方法: pip install selenium webdriver-manager")
    sys.exit(1)

BASE_URL = "https://trends-dashboard.fly.dev"
# ローカルテスト用
# BASE_URL = "http://localhost:5000"

def setup_driver():
    """Seleniumドライバーをセットアップ"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # ヘッドレスモード（ブラウザを表示しない）
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        if USE_WEBDRIVER_MANAGER:
            # webdriver-managerを使用して自動的にChromeDriverをダウンロード・管理
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # システムにインストールされたChromeDriverを使用
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.implicitly_wait(10)  # 要素が見つかるまで最大10秒待機
        return driver
    except Exception as e:
        print(f"❌ ドライバーのセットアップに失敗: {e}")
        if not USE_WEBDRIVER_MANAGER:
            print("webdriver-managerをインストールしてください: pip install webdriver-manager")
        print("または、ChromeDriverがインストールされているか確認してください")
        return None

def test_page_ui(driver, url, description, checks):
    """ページのUIをテスト"""
    try:
        print(f"\n{'='*60}")
        print(f"UIテスト: {description}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        driver.get(url)
        time.sleep(2)  # ページ読み込み待機
        
        # ページタイトルの確認
        page_title = driver.title
        print(f"✅ ページタイトル: {page_title}")
        
        # 各チェック項目を実行
        results = []
        for check_name, check_func in checks.items():
            try:
                result = check_func(driver)
                if result:
                    print(f"✅ {check_name}")
                    results.append(True)
                else:
                    print(f"⚠️  {check_name}: チェック失敗")
                    results.append(False)
            except Exception as e:
                print(f"❌ {check_name}: エラー - {str(e)}")
                results.append(False)
        
        return all(results)
        
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

def main():
    """メイン処理"""
    print(f"\n{'='*60}")
    print(f"UIテスト開始")
    print(f"テスト時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ベースURL: {BASE_URL}")
    print(f"{'='*60}")
    
    driver = setup_driver()
    if not driver:
        print("❌ ドライバーのセットアップに失敗しました")
        return 1
    
    results = []
    
    try:
        # 日本トレンドページのテスト
        def check_jp_page(driver):
            checks = {
                "ヘッダーが表示されている": lambda d: d.find_element(By.TAG_NAME, "header") is not None,
                "Google Trendsセクションが存在": lambda d: "Google Trends" in d.page_source,
                "YouTubeセクションが存在": lambda d: "YouTube" in d.page_source or "YouTube Trends" in d.page_source,
            }
            return all(check(driver) for check in checks.values())
        
        result = test_page_ui(
            driver,
            f"{BASE_URL}/",
            "日本トレンドページ",
            {
                "ページが読み込まれた": lambda d: d.find_element(By.TAG_NAME, "body") is not None,
                "ナビゲーションメニューが存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "a[href], button")) > 0,
                "トレンドセクションが存在": lambda d: "トレンド" in d.page_source or "Trends" in d.page_source,
            }
        )
        results.append(("日本トレンドページ", result))
        
        # USトレンドページのテスト
        result = test_page_ui(
            driver,
            f"{BASE_URL}/us",
            "USトレンドページ",
            {
                "ページが読み込まれた": lambda d: d.find_element(By.TAG_NAME, "body") is not None,
                "ナビゲーションメニューが存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "a[href], button")) > 0,
                "USトレンドセクションが存在": lambda d: "US" in d.page_source or "Trends" in d.page_source,
            }
        )
        results.append(("USトレンドページ", result))
        
        # データ鮮度情報ページのテスト
        result = test_page_ui(
            driver,
            f"{BASE_URL}/data-status",
            "データ鮮度情報ページ",
            {
                "ページが読み込まれた": lambda d: d.find_element(By.TAG_NAME, "body") is not None,
                "データ鮮度情報が表示されている": lambda d: "データ鮮度" in d.page_source or "Data Status" in d.page_source,
                "更新ボタンが存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "button, [role='button']")) > 0,
            }
        )
        results.append(("データ鮮度情報ページ", result))
        
        # サブスクリプションページのテスト
        result = test_page_ui(
            driver,
            f"{BASE_URL}/subscription/",
            "サブスクリプションページ",
            {
                "ページが読み込まれた": lambda d: d.find_element(By.TAG_NAME, "body") is not None,
                "メール入力フォームが存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "input[type='email'], input[name*='email']")) > 0,
                "配信頻度選択が存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "select, input[type='radio']")) > 0,
                "カテゴリ選択チェックボックスが存在": lambda d: len(d.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")) > 0,
            }
        )
        results.append(("サブスクリプションページ", result))
        
    finally:
        driver.quit()
    
    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"UIテスト結果サマリー")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for description, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status} - {description}")
    
    print(f"\n{'='*60}")
    print(f"合計: {success_count}/{total_count} 成功")
    print(f"成功率: {success_count/total_count*100:.1f}%")
    print(f"{'='*60}\n")
    
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())


# テストスクリプト

## test_pages.py

各ページとAPIエンドポイントの基本動作をテストするスクリプトです。

## test_ui.py

ブラウザを使用してUIの動作をテストするスクリプトです（Selenium使用）。

### 必要な準備

```bash
# Seleniumをインストール
pip install selenium

# ChromeDriverをインストール（macOSの場合）
brew install chromedriver

# または、ChromeDriverを手動でダウンロード
# https://chromedriver.chromium.org/downloads
```

### 使い方

```bash
# UIテストを実行
python tests/test_ui.py
```

### テスト内容

- 各ページが正しく読み込まれるか
- 必要なUI要素（ボタン、フォーム、メニューなど）が存在するか
- ページの基本構造が正しいか

### 使い方

```bash
# 本番環境をテスト
python tests/test_pages.py

# ローカル環境をテストする場合
# tests/test_pages.py の BASE_URL を "http://localhost:5000" に変更してから実行
```

### テスト内容

- **ページテスト**:
  - `/` - 日本トレンドページ
  - `/us` - USトレンドページ
  - `/data-status` - データ鮮度情報ページ
  - `/subscription/` - サブスクリプションページ

- **APIエンドポイントテスト**:
  - `/api/cache/data-freshness` - データ鮮度情報API
  - `/api/google-trends?region=JP` - Google Trends API
  - `/api/youtube-trends?region=JP` - YouTube Trends API
  - `/api/music-trends?service=spotify&region=JP` - Spotify Trends API
  - `/api/worldnews-trends?country=jp` - World News API
  - `/api/podcast-trends?trend_type=best_podcasts&region=jp` - Podcast Trends API
  - `/api/rakuten-trends` - 楽天トレンドAPI
  - `/api/hatena-trends?category=all` - はてなブックマークAPI
  - `/api/twitch-trends?category=games` - Twitch Trends API

### チェック項目

- ステータスコード（200を期待）
- コンテンツサイズ
- HTMLタグの存在
- エラーメッセージの有無
- JSON形式のレスポンス（APIの場合）


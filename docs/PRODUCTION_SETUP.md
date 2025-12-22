# 本番環境セットアップガイド

本番環境（Fly.io）での動作に必要な環境変数の設定方法を説明します。

## 🔑 必要な環境変数（APIキー）

本番環境で全てのトレンドデータを取得するには、以下のAPIキーを設定する必要があります。

### 1. データベース接続

```bash
# Fly.ioでPostgreSQLをアタッチすると自動設定されます
DATABASE_URL  # 自動設定（手動設定不要）
```

### 2. 必須APIキー

以下のAPIキーは、対応するトレンドデータを取得するために必要です。

```bash
# News API（Newsトレンド）
NEWS_API_KEY="your-news-api-key"

# World News API（World Newsトレンド）
WORLDNEWS_API_KEY="your-world-news-api-key"

# Listen Notes API（Podcastトレンド）
LISTEN_API_KEY="your-listen-api-key"

# 楽天API（楽天トレンド）
RAKUTEN_APP_ID="your-rakuten-app-id"
RAKUTEN_AFFILIATE_ID="your-rakuten-affiliate-id"

# Twitch API（Twitchトレンド）
TWITCH_CLIENT_ID="your-twitch-client-id"
TWITCH_CLIENT_SECRET="your-twitch-client-secret"

# YouTube API（YouTubeトレンド）
YOUTUBE_API_KEY="your-youtube-api-key"

# Spotify API（音楽トレンド）
SPOTIFY_CLIENT_ID="your-spotify-client-id"
SPOTIFY_CLIENT_SECRET="your-spotify-client-secret"
```

### 3. Google Cloud認証（Google Trends用）

```bash
# サービスアカウントキーのBase64エンコードされた内容
GOOGLE_APPLICATION_CREDENTIALS_CONTENT="$(cat /path/to/service-account-key.json | base64)"
```

または、Dockerfileでファイルをコピーする方法：

```dockerfile
COPY service-account-key.json /app/service-account-key.json
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/service-account-key.json"
```

### 4. メール送信設定（サブスクリプション機能用）

```bash
SENDER_EMAIL="your-email@gmail.com"
SENDER_PASSWORD="your-email-password"
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
```

## 📝 本番環境への設定方法

### Fly.ioでの設定

1. **全APIキーを一括設定**（推奨）

```bash
fly secrets set \
  NEWS_API_KEY="your-news-api-key" \
  WORLDNEWS_API_KEY="your-world-news-api-key" \
  LISTEN_API_KEY="your-listen-api-key" \
  RAKUTEN_APP_ID="your-rakuten-app-id" \
  RAKUTEN_AFFILIATE_ID="your-rakuten-affiliate-id" \
  TWITCH_CLIENT_ID="your-twitch-client-id" \
  TWITCH_CLIENT_SECRET="your-twitch-client-secret" \
  YOUTUBE_API_KEY="your-youtube-api-key" \
  SPOTIFY_CLIENT_ID="your-spotify-client-id" \
  SPOTIFY_CLIENT_SECRET="your-spotify-client-secret" \
  SENDER_EMAIL="your-email@gmail.com" \
  SENDER_PASSWORD="your-email-password" \
  SMTP_SERVER="smtp.gmail.com" \
  SMTP_PORT="587" \
  -a trends-dashboard
```

2. **Google Cloud認証情報の設定**

```bash
# Base64エンコードされた内容を設定
fly secrets set GOOGLE_APPLICATION_CREDENTIALS_CONTENT="$(cat /path/to/service-account-key.json | base64)" -a trends-dashboard
```

3. **設定の確認**

```bash
fly secrets list -a trends-dashboard
```

## ⚠️ 注意事項

1. **APIキーが設定されていない場合**
   - 該当するトレンドデータは取得されません
   - エラーメッセージがログに記録されます
   - 他のトレンドデータは正常に取得されます

2. **データベース接続エラー**
   - 本番環境では、アプリケーションが自動停止（`auto_stop_machines = true`）されることがあります
   - この場合、データベース接続が閉じられますが、最新の修正により自動的に再接続されます
   - 初回リクエスト時は少し遅延する可能性があります

3. **環境変数の変更後**
   - 環境変数を変更した後は、アプリケーションを再起動する必要があります：
   ```bash
   fly deploy -a trends-dashboard
   ```

## 🔍 トラブルシューティング

### APIキーエラーが発生する場合

1. 環境変数が正しく設定されているか確認：
   ```bash
   fly secrets list -a trends-dashboard
   ```

2. アプリケーションのログを確認：
   ```bash
   fly logs -a trends-dashboard
   ```

3. 特定のトレンドデータが取得できない場合、対応するAPIキーが設定されているか確認してください

### データベース接続エラーが発生する場合

1. データベースが正常に動作しているか確認：
   ```bash
   fly postgres list -a trends-dashboard
   ```

2. DATABASE_URLが正しく設定されているか確認：
   ```bash
   fly secrets list -a trends-dashboard | grep DATABASE_URL
   ```

3. アプリケーションのログを確認して、再接続が試みられているか確認：
   ```bash
   fly logs -a trends-dashboard | grep -i "データベース接続"
   ```

## 📊 動作確認

全ての環境変数を設定した後、以下のコマンドで本番環境のデータを更新して確認できます：

```bash
curl -X POST "https://trends-dashboard.fly.dev/api/cache/refresh-all?force_refresh=true"
```

成功した場合、各カテゴリの`success: true`が返されます。


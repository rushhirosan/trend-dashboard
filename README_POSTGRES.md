# PostgreSQL キャッシュシステム設定ガイド

## 🗄️ 概要

このアプリケーションは、Google TrendsデータをPostgreSQLデータベースにキャッシュして、高速な表示を実現します。

## 🚀 特徴

- **1日1回のみ**BigQueryからデータ取得
- **表示時はDBから高速取得**
- **データの有効期限管理**（24時間）
- **fly.dev対応**

## 📋 必要な環境変数

```bash
# PostgreSQL接続情報
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=trends_cache
export DB_USER=postgres
export DB_PASSWORD=your_password

# Google Cloud認証（既存）
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

## 🛠️ セットアップ手順

### 1. PostgreSQLのインストール

#### macOS (Homebrew)
```bash
brew install postgresql
brew services start postgresql
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. データベースとユーザーの作成

```bash
# PostgreSQLに接続
sudo -u postgres psql

# データベース作成
CREATE DATABASE trends_cache;

# ユーザー作成
CREATE USER trends_user WITH PASSWORD 'your_password';

# 権限付与
GRANT ALL PRIVILEGES ON DATABASE trends_cache TO trends_user;

# 接続終了
\q
```

### 3. 環境変数の設定

```bash
# .envファイルを作成
cat > .env << EOF
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trends_cache
DB_USER=trends_user
DB_PASSWORD=your_password
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
EOF

# 環境変数を読み込み
source .env
```

### 4. アプリケーションの起動

```bash
python -m streamlit run apps/bigquery_trends_app.py --server.port 8502
```

## 🗂️ データベース構造

### trends_cache テーブル
- `id`: 主キー
- `country_code`: 国コード（JP, US等）
- `term`: トレンドキーワード
- `rank`: 順位
- `score`: スコア
- `region_count`: トレンド地域数
- `week`: 週（日付）
- `created_at`: 作成日時

### cache_status テーブル
- `id`: 主キー
- `country_code`: 国コード
- `last_updated`: 最終更新日時
- `data_count`: データ件数

## 🔄 キャッシュの動作

1. **初回アクセス**: BigQueryからデータ取得 → DBに保存
2. **24時間以内**: DBから高速取得
3. **24時間経過**: 自動的にBigQueryから再取得 → DB更新

## 🚀 fly.dev デプロイ

### fly.toml 設定例

```toml
[env]
  DB_HOST = "your-postgres-host.internal"
  DB_PORT = "5432"
  DB_NAME = "trends_cache"
  DB_USER = "trends_user"
  DB_PASSWORD = "your_password"
  GOOGLE_APPLICATION_CREDENTIALS = "/app/service-account-key.json"

[[services]]
  internal_port = 8502
  processes = ["app"]
  protocol = "tcp"
  script_checks = []
  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"
```

### PostgreSQL アドオンの追加

```bash
fly postgres create --name trends-db
fly postgres attach trends-db --app your-app-name
```

## 📊 パフォーマンス

- **初回**: BigQuery API呼び出し（数秒）
- **キャッシュヒット**: DBクエリ（数ミリ秒）
- **データ更新**: 24時間ごとに自動

## 🔧 トラブルシューティング

### 接続エラー
```bash
# PostgreSQLの状態確認
sudo systemctl status postgresql

# 接続テスト
psql -h localhost -U trends_user -d trends_cache
```

### 権限エラー
```bash
# ユーザー権限確認
sudo -u postgres psql -c "\du"
```

### データベース初期化エラー
```bash
# ログ確認
tail -f /var/log/postgresql/postgresql-*.log
```

## 📝 注意事項

- 初回起動時は自動的にテーブルが作成されます
- キャッシュは24時間で自動的に無効化されます
- BigQueryの認証設定が必要です
- データベースのバックアップを定期的に取得することを推奨します 
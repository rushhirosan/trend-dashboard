# Fly.io デプロイ手順

## 前提条件

1. Fly.ioアカウントを作成: https://fly.io
2. Fly CLIをインストール: `curl -L https://fly.io/install.sh | sh`
3. ログイン: `fly auth login`

## デプロイ手順

### 1. PostgreSQLデータベースの作成（無料枠）

```bash
# 無料枠でPostgreSQLを作成（最小サイズのVMを指定）
fly postgres create \
  --name trends-db \
  --region nrt \
  --vm-size shared-cpu-1x \
  --vm-memory 256 \
  --volume-size 1 \
  --initial-cluster-size 1
```

**無料枠の設定**:
- `--vm-size shared-cpu-1x`: 共有CPU、最小サイズ
- `--vm-memory 256`: メモリ256MB（無料枠内）
- `--volume-size 1`: ストレージ1GB（無料枠内、必要に応じて調整可能）
- `--initial-cluster-size 1`: クラスタサイズ1（HA不要、無料枠内）
- これにより、無料枠（VM 3つまで、ストレージ3GBまで）内で運用できます
- ストレージは1GBで十分な場合は1GB、必要に応じて3GBまで増やすことができます

**注意**: 
- `--initial-cluster-size 1`を指定すると、単一インスタンスで作成されます（HA不要）
- デフォルトの3は高可用性（HA）用で、3つのVMが必要です（無料枠を超える可能性があります）
- 作成時にパスワードの入力を求められる場合があります（空白で自動生成も可能）
- データベース作成後、接続情報が表示されます

### 2. アプリケーションの初期化（初回のみ）

```bash
fly launch --no-deploy
```

### 3. アプリケーションにPostgreSQLをアタッチ

```bash
# アプリケーションにPostgreSQLをアタッチ（DATABASE_URLが自動設定されます）
fly postgres attach trends-db -a trends-dashboard
```

### 4. ローカルDBスキーマを本番環境にコピー

ローカルのテーブル構造を本番環境にコピーする場合：

# 1. ローカルDBのスキーマをダンプ
# 2. DATABASE_URLを設定（fly.ioから取得）
# 3. 本番環境に適用
```bash
# 1. ローカルDBのスキーマをダンプ
pg_dump --schema-only --no-owner --no-privileges \
  -h localhost -U postgres -d trends_db > local_schema.sql

# 2. DATABASE_URLを設定（fly.ioから取得）
export DATABASE_URL="postgresql://..."

# 3. 本番環境に適用
psql $DATABASE_URL < local_schema.sql
```

詳細は `docs/COPY_SCHEMA.md` を参照してください。

### 5. 環境変数の設定

# その他の環境変数を設定
fly secrets set \
  SECRET_KEY="your-secret-key" \
  GOOGLE_APPLICATION_CREDENTIALS="/app/service-account-key.json" \
  SPOTIFY_CLIENT_ID="your-spotify-client-id" \
  SPOTIFY_CLIENT_SECRET="your-spotify-client-secret" \
  NEWS_API_KEY="your-news-api-key" \
  WORLD_NEWS_API_KEY="your-world-news-api-key" \
  LISTEN_API_KEY="your-listen-api-key" \
  RAKUTEN_APP_ID="your-rakuten-app-id" \
  RAKUTEN_AFFILIATE_ID="your-rakuten-affiliate-id" \
  TWITCH_CLIENT_ID="your-twitch-client-id" \
  TWITCH_CLIENT_SECRET="your-twitch-client-secret" \
  SENDER_EMAIL="your-email@gmail.com" \
  SENDER_PASSWORD="your-email-password" \
  SMTP_SERVER="smtp.gmail.com" \
  SMTP_PORT="587" \
  -a trends-dashboard
```

### 6. Google Cloud認証情報のアップロード

```bash
# サービスアカウントキーファイルをアップロード
fly secrets set GOOGLE_APPLICATION_CREDENTIALS_CONTENT="$(cat /path/to/service-account-key.json | base64)" -a trends-dashboard
```

または、Dockerfileでコピーする方法：

```dockerfile
COPY service-account-key.json /app/service-account-key.json
```

### 7. デプロイ

```bash
fly deploy -a trends-dashboard
```

### 8. アプリケーションの確認

```bash
# ログを確認
fly logs -a trends-dashboard

# アプリケーションの状態を確認
fly status -a trends-dashboard

# アプリケーションのURLを確認
fly open -a trends-dashboard
```

## トラブルシューティング

### データベース接続エラー

```bash
# データベースの状態を確認
fly postgres status -a trends-db

# 接続情報を確認
fly postgres connect -a trends-db
```

### 環境変数の確認

```bash
fly secrets list -a trends-dashboard
```

### ログの確認

```bash
fly logs -a trends-dashboard
```

## 注意事項

- 初回デプロイ後、データベースのテーブルが自動的に作成されます
- スケジューラーは毎日朝5時に自動実行されます
- 環境変数は`fly secrets`コマンドで設定してください（.envファイルは使用されません）


# ローカルDBスキーマを本番環境にコピーする方法

ローカル PostgreSQL のスキーマを fly.io 上の本番データベースへ反映するための手順です。自動化スクリプトは削除したため、以下の手順を直接実行してください。

## 1. 前提

- ローカルで PostgreSQL が動作していること  
- `fly` CLI にログイン済みで、`trends-dashboard` / `trends-db` の権限があること  
- `.env` などにローカル DB の接続情報が保存されていること

## 2. ローカルスキーマのダンプ

```bash
source .env  # 必要であれば

pg_dump \
  --host="${DB_HOST:-localhost}" \
  --port="${DB_PORT:-5432}" \
  --username="${DB_USER:-postgres}" \
  --dbname="${DB_NAME:-trends_db}" \
  --schema-only \
  --no-owner \
  --no-privileges \
  > local_schema.sql
```

## 3. 本番 DATABASE_URL の取得

```bash
export DATABASE_URL=$(fly secrets list -a trends-dashboard \
  | grep DATABASE_URL | awk '{print $2}')
```

プロキシ経由で接続する場合は別ターミナルで `fly proxy 5433 -a trends-db` を起動し、  
`DATABASE_URL` のホスト名／ポートを `localhost:5433` に書き換えてください。

## 4. スキーマの適用

```bash
psql "$DATABASE_URL" < local_schema.sql
```

問題がなければ `local_schema.sql` は削除して構いません。

## 補足

- ダンプはテーブル構造のみでデータは含みません。データ移行が必要なら `pg_dump --data-only` を利用してください。
- 既存テーブルへは `CREATE TABLE IF NOT EXISTS` で作成しているため、スキーマ差異がある場合は手動調整が必要です。
- `fly ssh console -a trends-dashboard` でマシンへ入り、`psql $DATABASE_URL` を直接実行しても構いません。

## トラブルシューティング

- 接続エラー: `psql -h localhost -U postgres -d trends_db -c "SELECT 1"` でローカル DB を確認  
- 権限エラー: `psql ... -c "\du"` で権限を確認  
- スキーマ差分: `pg_dump --schema-only` の出力をファイルに保存し、本番側の `pg_dump` と `diff` で比較してください。


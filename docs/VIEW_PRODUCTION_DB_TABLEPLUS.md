# 本番 Postgres を TablePlus で見る（fly proxy）

`fly secrets list` の `DATABASE_URL` は DIGEST のみ表示される。接続情報の平文はアプリ VM 上の環境変数から取る。

## 手順

1. **接続文字列（平文）** — 一度だけでよい  
   ```bash
   fly ssh console -a trends-dashboard
   printenv DATABASE_URL
   exit
   ```  
   表示された URL の **ホストを `localhost`、ポートを `5433`** に差し替え、TablePlus の User / Password / Database に反映（または URL をそのまま編集して接続テスト）。

2. **プロキシ** — データを見るたび、**別ターミナルで起動したまま**にする  
   ```bash
   fly proxy 5433:5432 -a trends-db
   ```  
   `-a` は Fly 上の **Postgres アプリ名**（例: `trends-db`。`fly apps list` で確認）。

3. **TablePlus** — PostgreSQL 接続  
   - Host: `localhost`  
   - Port: `5433`（プロキシの左側と一致）  
   - User / Password / Database: Step 1 の URL から  
   - SSL: エラー時は Prefer または Disable を試す  

   保存した接続はメイン画面左で **ダブルクリック**で開く。

## トラブル

- **`Connection refused` on `localhost:5433`** — `fly proxy` が動いていない、またはポートが違う。プロキシを立て直し、TablePlus の Port を合わせる。

## 名前が違う場合

- Web アプリ: `trends-dashboard` → 実際の `fly.toml` / `fly apps list` の名前  
- Postgres: `trends-db` → `fly postgres list` 等で確認

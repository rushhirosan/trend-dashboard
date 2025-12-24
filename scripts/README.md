# Scripts

このディレクトリには、デバッグやメンテナンス用のスクリプトが含まれています。

## ファイル一覧

### check_cache.py
データベースのキャッシュデータを確認するスクリプト（ローカル環境用）

**使用方法:**
```bash
python scripts/check_cache.py
```

### check_cache_remote.py
リモート環境（fly.io）でのキャッシュデータ確認用スクリプト  
**7時の更新確認機能付き** - 全カテゴリが今日の7時（JST）に更新されたかを確認します

**使用方法:**

#### 方法1: Fly.ioのリモート環境で実行（推奨）
```bash
# Fly.ioのリモート環境に接続
fly ssh console -a trends-dashboard

# スクリプトを実行（DATABASE_URLは自動的に設定されています）
python scripts/check_cache_remote.py
```

#### 方法2: ローカルからリモートDBに接続
```bash
# DATABASE_URLを設定（Fly.ioのシークレットから取得）
export DATABASE_URL=$(fly secrets list -a trends-dashboard | grep DATABASE_URL | awk '{print $2}')

# または、直接DATABASE_URLを設定
export DATABASE_URL='postgresql://user:password@host:port/database'

# スクリプトを実行
python scripts/check_cache_remote.py
```

**出力内容:**
- キャッシュテーブルのデータ件数
- 7時の更新確認（各カテゴリが今日の7時に更新されたか）
- 更新済み/未更新の件数

### check_cache_status.py
タイムアウトしているカテゴリのキャッシュデータ件数を確認するスクリプト

**使用方法:**
```bash
python scripts/check_cache_status.py
```

## 注意事項

- これらのスクリプトは開発・デバッグ用です
- 本番環境で実行する場合は、事前にデータベース接続情報を確認してください
- 環境変数（`.env`）が正しく設定されていることを確認してください

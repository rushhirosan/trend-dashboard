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

**使用方法:**
```bash
fly ssh console -a trends-dashboard
python scripts/check_cache_remote.py
```

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

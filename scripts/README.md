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

### update_book_trends.py
本トレンドの全カテゴリをAPIから取得しキャッシュを更新するスクリプト

**使用方法:**
```bash
python scripts/update_book_trends.py
```

**動作:**
- 日本: 総合・文芸・ビジネス・人文・社会・実用・IT の5カテゴリを楽天ブックスAPIから取得
- US: All, Fiction, Business, Biography & History, Science & Tech の5カテゴリをGoogle Books APIから取得

### bootstrap_dummy_cache.py
全カテゴリにダミーデータ（Lorem ipsum）を25件ずつキャッシュするスクリプト
ローカル開発環境でUI/UXの確認用に使用

**使用方法:**
```bash
python scripts/bootstrap_dummy_cache.py
```

**動作:**
1. 全カテゴリのマネージャーに対してダミーモードで25件ずつダミーデータを生成
2. 生成したダミーデータをデータベースキャッシュに保存
3. 以降、通常モードでアプリを起動してもキャッシュからダミーデータが表示される

**注意:**
- このスクリプトは既存のキャッシュデータを上書きします
- 外部APIキーは不要です（ダミーモードのため）
- 一度実行すれば、その後は通常モードでアプリを起動するだけでダミーデータが表示されます

## 注意事項

- これらのスクリプトは開発・デバッグ用です
- 本番環境で実行する場合は、事前にデータベース接続情報を確認してください
- 環境変数（`.env`）が正しく設定されていることを確認してください

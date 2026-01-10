# ローカル環境セットアップガイド

このガイドでは、ローカル環境でtrend-dashboardを動作させるための手順を説明します。

## 📋 前提条件

- Python 3.11以上（推奨: 3.11または3.12）
- pip（Pythonパッケージマネージャー）
- （オプション）PostgreSQL - データベース接続なしでもアプリは起動しますが、データは表示されません

## 🚀 セットアップ手順

### 1. 仮想環境（venv）の作成と有効化

```bash
# 仮想環境を作成（既に存在する場合はスキップ）
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 2. 依存関係のインストール

```bash
# 仮想環境が有効化されていることを確認
which python  # venv/bin/python を指しているはず

# 依存関係をインストール
pip install -r requirements.txt
```

**注意**: Python 3.14を使用している場合、`psycopg2-binary`のインストールでエラーが発生する可能性があります。その場合は、PostgreSQLをインストールするか、データベース接続なしで動作確認してください。

### 3. 環境変数の設定

`.env`ファイルがプロジェクトルートに存在することを確認してください。存在しない場合は、以下の内容で作成します：

```bash
# .envファイルの内容（最小構成）
FLASK_PORT=5000
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
HOST=0.0.0.0

# データベース接続（PostgreSQLがインストールされている場合のみ）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trends_db
DB_USER=postgres
DB_PASSWORD=password

# Amazon Best Sellers RSS URL（AmaranRSS等で生成したRSS URLを設定）
# 複数のRSS URLをカンマ区切りで指定可能
# 例: AMAZON_RSS_URLS=https://livdir.com/am-tb/xxxx.rss,https://livdir.com/am-tb/yyyy.rss
# 注意: 1時間に1回以上の取得は避けてください（AmaranRSSの推奨）
AMAZON_RSS_URLS=
```

### 4. アプリケーションの起動

```bash
# 仮想環境が有効化されていることを確認
source venv/bin/activate

# アプリケーションを起動
python app.py
```

ブラウザで `http://localhost:5000` にアクセスしてアプリケーションを確認できます。

## 🗄️ PostgreSQLのセットアップ（オプション）

データベース接続なしでもアプリは起動しますが、トレンドデータを表示するにはPostgreSQLが必要です。

### macOS (Homebrew)

```bash
# PostgreSQLをインストール
brew install postgresql

# PostgreSQLを起動
brew services start postgresql

# データベースを作成
createdb trends_db
```

### データベース接続の確認

```bash
# PostgreSQLに接続できるか確認
psql -h localhost -U postgres -d trends_db
```

接続できない場合は、`.env`ファイルのデータベース設定を確認してください。

## 🔧 トラブルシューティング

### psycopg2のインストールエラー

Python 3.14などの新しいバージョンでは、`psycopg2-binary`のビルド済みホイールが利用できない場合があります。

**解決策**:
1. PostgreSQLをインストールして`pg_config`を利用可能にする
2. または、Python 3.11または3.12を使用する

### データが表示されない

データベース接続がない場合、アプリケーションは起動しますが、データは表示されません。これは正常な動作です。

**解決策**:
1. PostgreSQLをインストール・起動する
2. `.env`ファイルに正しいデータベース接続情報を設定する
3. または、本番環境（fly.io）で確認する

### 仮想環境が有効化されない

```bash
# 仮想環境を再作成
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📝 次のステップ

- 本番環境へのデプロイ: `docs/DEPLOY.md`を参照
- データベーススキーマのコピー: `docs/COPY_SCHEMA.md`を参照
- APIキーの設定: `docs/PRODUCTION_SETUP.md`を参照


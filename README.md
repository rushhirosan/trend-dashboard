# Trends Dashboard

日本とUSの最新トレンド情報を一括表示するWebアプリケーション

**公式サイト / Live:** [https://trends-dashboard.fly.dev/](https://trends-dashboard.fly.dev/) — 日本（`/`）と米国（`/us`）の公開トレンド信号を1画面でざっと掴む個人製作のダッシュボード。投資助言や各サービスの正規データの代替ではありません。

## 🌐 ライブサイト

- **日本トレンド**: https://trends-dashboard.fly.dev/
- **USトレンド**: https://trends-dashboard.fly.dev/us
- **データ鮮度**: https://trends-dashboard.fly.dev/data-status
- **メールサブスクリプション**: https://trends-dashboard.fly.dev/subscription

## 📊 機能

### 対応しているトレンド

**日本トレンド:**
- NHK ニュース
- World News
- Google Trends
- YouTube Trends
- はてなブックマーク
- Qiita トレンド
- Zenn
- Note
- Wikipedia 人気記事（日本語）
- IPA注意喚起・JPCERT/CC
- GitHub Trends
- App Store Trends
- 株価トレンド
- 仮想通貨トレンド
- 映画トレンド
- 本トレンド
- Spotify 音楽トレンド
- Podcast トレンド
- 楽天商品トレンド
- Twitch ゲームトレンド
- OpenAlex 学術論文トレンド
- Bluesky トレンド

**USトレンド:**
- CNN News
- World News
- Google Trends
- YouTube Trends
- Hacker News
- Product Hunt
- DEV.to
- Medium
- CISA KEV・The Hacker News
- Wikipedia Most Read（英語）
- GitHub Trends
- App Store Trends
- 株価トレンド
- 仮想通貨トレンド
- 映画トレンド
- 本トレンド
- Spotify 音楽トレンド
- Podcast トレンド
- eBay Popular/Trending
- Twitch ゲームトレンド
- OpenAlex 学術論文トレンド
- Bluesky トレンド

### 主な機能

- 📈 **リアルタイムトレンド表示**: 各プラットフォームの最新トレンドを一覧表示
- 📧 **メールサブスクリプション**: 毎日1時、7時、13時、19時（JST）に更新処理を開始し、完了次第トレンドサマリーをメール配信（完了までおおむね25〜45分かかることがあります）
- 📊 **データ鮮度情報**: 各トレンドデータの最終更新時刻とデータ件数を確認
- 🔄 **自動更新**: 毎日1時、7時、13時、19時（JST）に更新処理を開始（完了までおおむね25〜45分かかることがあります）
- 💾 **キャッシュシステム**: PostgreSQLを使用した高速なデータ取得

## 🛠️ 技術スタック

- **Backend**: Python 3.11, Flask
- **Database**: PostgreSQL
- **Frontend**: HTML, CSS (Bootstrap), JavaScript (Vanilla JS/jQuery)
- **Deployment**: Fly.io
- **Scheduler**: APScheduler

## 📋 セットアップ

### 前提条件

- Python 3.11以上
- PostgreSQL
- 各種APIキー（後述）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/rushhirosan/trend-dashboard.git
cd trend-dashboard

# 依存関係をインストール
pip install -r requirements.txt
```

### 環境変数の設定

`.env`ファイルを作成し、必要な環境変数を設定してください。

詳細なセットアップ手順と必要な環境変数の一覧は [`docs/PRODUCTION_SETUP.md`](docs/PRODUCTION_SETUP.md) を参照してください。

### アプリケーションの起動

```bash
python app.py
```

アプリケーションは `http://localhost:5000` で起動します。

## 🚀 デプロイ

Fly.ioへのデプロイ手順は [`docs/DEPLOY.md`](docs/DEPLOY.md) を参照してください。

## 📁 プロジェクト構造

```
trends_dashboard/
├── app.py                 # メインアプリケーション
├── wsgi.py               # WSGIエントリーポイント
├── database_config.py     # データベース設定とキャッシュ管理
├── config/               # アプリケーション設定
├── managers/             # トレンドマネージャーの管理
├── routes/               # APIルート定義
├── services/             # ビジネスロジック
│   ├── scheduler/        # スケジューラー
│   ├── subscription/     # メールサブスクリプション
│   └── trends/           # 各トレンドサービスの実装
├── static/               # 静的ファイル（CSS, JavaScript）
├── templates/            # HTMLテンプレート
├── utils/                # ユーティリティ関数
└── docs/                 # ドキュメント
```

## 📝 データ更新スケジュール

- **自動更新**: 毎日1:00、7:00、13:00、19:00（JST）にスケジューラーが実行
- **メール配信**: データ更新完了後、自動的にメール送信（7:20頃、13:20頃、19:20頃）
- **キャッシュ**: 更新間隔中はキャッシュデータを使用

## 🔒 セキュリティ

- APIキーは環境変数から読み込み（ハードコードなし）
- `.env`ファイルと`*.json`ファイルは`.gitignore`に含まれています
- 機密情報はGitHubにpushされません

## 📄 ライセンス

MIT License

## 🤝 コントリビューション

プルリクエストやイシューの報告を歓迎します！

## 📚 ドキュメント

詳細なドキュメントは [`docs/`](docs/) ディレクトリを参照してください。

- [プロジェクト仕様書](docs/spec.md)
- [デプロイ手順](docs/DEPLOY.md)
- [本番環境セットアップ](docs/PRODUCTION_SETUP.md)
- [API価格分析](docs/API_PRICING_ANALYSIS.md)


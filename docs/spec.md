# プロジェクト名

トレンドダッシュボード

## 概要

その日のトレンドの一覧が見れる。一覧の対象は、
- Googleトレンド
- YouTube
- ワールドニュース
- Spotify(USの場合はGlobal trend)
- はてなブックマーク天(日本のみ)
- Reddit(USのみ)
- Podcast
- 楽天(日本のみ)
- Twitch

## クイックスタート

ウェブで閲覧するアプリ
メールをサブスクライブすることによってトレンドサマリーを受信することができる

## アーキテクチャ概要

### 技術スタック：
Python, Flask

### デプロイ先：
fly.io

### 主要ディレクトリ：
* ディレクトリ構成を抜き出す

### データフロー：

**定期実行（スケジューラー）:**
- 朝7:00（日本時間） → スケジューラー実行 → 全API呼び出し → キャッシュ更新 → メール自動送信
- 昼14:00（日本時間） → スケジューラー実行 → 全API呼び出し → キャッシュ更新 → メール自動送信

**通常時:**
- 朝7:01〜夜11:59 → 1日1回制限によりキャッシュデータ使用
- 夜12:00〜朝6:59 → 時間外制限によりキャッシュデータ使用

**デプロイ時:**
- デプロイ時は自動実行・メール送信をスキップ（`SKIP_STARTUP_EXECUTION=true`）
- データ更新はスケジューラー（1日2回）と明示的な手動実行のみに依存

**キャッシュ管理:**
- キャッシュデータは日本とUS/グローバル別々に管理している

### 手動更新と手動実行の違い

データ更新には2つの方法があります：

#### 1. 手動更新 (`POST /api/cache/refresh-all`)

**エンドポイント:**
```
POST /api/cache/refresh-all?force_refresh=true
```

**特徴:**
- `refresh_all_trends()` を直接呼び出し
- スケジューラーのロジックを通さない（実行履歴の記録なし）
- メール送信: 環境変数 `SKIP_EMAIL_ON_UPDATE` で制御（デフォルトは `false` = 送信される）
- 用途: データ管理画面からの即時更新

**パラメータ:**
- `force_refresh`: 省略可（デフォルト `true`）

**使用例:**
```bash
# 全カテゴリーを強制更新（メール送信あり）
curl -X POST "http://localhost:5000/api/cache/refresh-all?force_refresh=true"

# 個別カテゴリの強制更新
curl -s "http://localhost:5000/api/youtube-trends?region=JP&force_refresh=true"
curl -s "http://localhost:5000/api/worldnews-trends?country=jp&force_refresh=true"
curl -s "http://localhost:5000/api/podcast-trends?trend_type=best_podcasts&force_refresh=true"
```

#### 2. 手動実行 (`POST /api/scheduler/execute`)

**エンドポイント:**
```
POST /api/scheduler/execute
```

**特徴:**
- スケジューラーの `_fetch_all_trends(force=True)` を呼び出し
- スケジューラーのロジックを通す（実行履歴の記録、重複実行チェックなど）
- メール送信: スキップされる（`force=True` の場合）
- 用途: スケジューラーと同じ処理フローで実行したい場合

**使用例:**
```bash
# スケジューラーを手動実行（メール送信なし）
curl -X POST "http://localhost:5000/api/scheduler/execute"
```

#### 比較表

| 項目 | 手動更新 | 手動実行 |
|------|---------|---------|
| エンドポイント | `POST /api/cache/refresh-all` | `POST /api/scheduler/execute` |
| 実行履歴の記録 | ❌ なし | ✅ あり |
| 重複実行チェック | ❌ なし | ✅ あり（`force=True` でスキップ） |
| メール送信 | ✅ あり（環境変数で制御可能） | ❌ なし |
| スケジューラーロジック | ❌ 通さない | ✅ 通す |

**データ確認:**
```bash
curl -s "http://localhost:5000/api/cache/data-freshness" \
  | python -c 'import sys, json; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))'
```

### メールサブスクリプション機能

#### 概要
ユーザーはメールアドレスを登録することで、トレンドサマリーをメールで受信できます。

#### 登録方法
- `/subscription` ページからメールアドレス、配信頻度（毎日/毎週/毎月）、配信カテゴリを選択して登録
- 登録確認メールが自動送信される

#### メール送信について

**自動送信機能（実装済み）:**

- ✅ スケジューラーによる自動更新（朝7:00・昼14:00 日本時間）完了後に自動的にメール送信
- ✅ 手動更新（`POST /api/cache/refresh-all`）完了後にも自動的にメール送信（環境変数 `SKIP_EMAIL_ON_UPDATE=false` の場合）
- ❌ 手動実行（`POST /api/scheduler/execute`）ではメール送信をスキップ
- ❌ デプロイ時は自動実行・メール送信をスキップ（`SKIP_STARTUP_EXECUTION=true`）
- メール送信失敗がスケジューラー全体を止めないようにエラーハンドリング済み

#### 手動メール送信方法（管理者用）

必要に応じて、管理者用APIエンドポイントから手動実行も可能です：

**コマンドラインから実行:**

```bash
# ローカル環境
curl -X POST "http://localhost:5000/subscription/api/send-trends-summary" \
  -H "Content-Type: application/json"

# 本番環境
curl -X POST "https://trends-dashboard.fly.dev/subscription/api/send-trends-summary" \
  -H "Content-Type: application/json"
```

このエンドポイントを実行すると、アクティブな全サブスクリプションに対してトレンドサマリーメールが送信されます。

### ログとモニタリング

#### ログシステム
- ✅ プロジェクト全体で`print()`を`logging`モジュールに統一（422箇所）
- ✅ 統一的なログ設定モジュール（`utils/logger_config.py`）
- ✅ 環境変数`LOG_LEVEL`でログレベルを制御可能
- ログフォーマット: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

#### ヘルスチェック
- ✅ `/health` エンドポイントでアプリケーションの状態を確認可能
- チェック項目:
  - データベース接続状態と応答時間
  - トレンドマネージャーの初期化状態
  - キャッシュの状態（最終更新時刻、データ数）
  - スケジューラーの状態（初期化、実行中）
- レスポンスコード:
  - `200`: すべて正常（healthy）
  - `503`: 一部またはすべてが異常（degraded）

### 環境変数
.env

## 生成AIによるサマリー生成検討

chat gpt 3.5 -> 2021年まで
chat gpt 4 -> 高すぎる
claude-3 Haiku -> 2023年まで
gemini -> 
Custom Search APIの廃止問題
Vertex AI Searchのドメイン所有権問題
Claude-3 Haikuの精度問題
Bing Searchも高い

## ローカルポート

5000

## 検討したプラットフォーム

ジャンル	プラットフォーム例	API利用可否
ソーシャル	Twitter(X), Reddit, Threads, Facebook	◯（一部有料）
動画・配信	YouTube, TikTok, Twitch	◯
音楽・音声	Spotify, Apple Music, ListenNotes	◯
ニュース	Google News, NewsWhip, 各社API	◯
ショッピング	Amazon, 楽天, Yahoo!ショッピング	◯
ライフスタイル	Pinterest, Snapchat	◯（限定的）
reddit -> なし
qiita
はてぶ
Twitch
tweepy
Social Blade API: 統計データ







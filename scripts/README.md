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

**ローカルでの使用方法:**
```bash
python scripts/update_book_trends.py
```

**本番（Fly.io）での実行:**
```bash
# 1. 本番マシンに SSH で入る
fly ssh console -a trends-dashboard

# 2. コンテナ内でスクリプトを実行（WORKDIR は /app）
python scripts/update_book_trends.py

# 3. 終了
exit
```
本番では `fly secrets` で設定した `RAKUTEN_APP_ID` と `GOOGLE_BOOKS_API_KEY` が使われ、楽天・Google Books API から実データが取得されます。

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

### scaffold_summary_drafts.py
`docs/summaries/` 以下に、サマリー用の空 Markdown をテンプレから生成する（X ポストサンプルと同様、**リポジトリに下書きを積む**運用向け）。

**使用方法:**
```bash
python scripts/scaffold_summary_drafts.py --today
python scripts/scaffold_summary_drafts.py --daily 2026-05-11
python scripts/scaffold_summary_drafts.py --weekly-for-date 2026-06-01
python scripts/scaffold_summary_drafts.py --today --weekly-for-date 2026-05-11 --force
```

**注意:** 同名ファイルがある場合はスキップする。上書きは `--force`。

詳細は `docs/summaries/README.md` を参照。

### generate_ai_daily_summary.py
`DATABASE_URL` の `trend_daily_snapshots`（前日 × スロット 07/13/19/01）から OpenAI で日次サマリーを書く。**`--write`** 時は **`docs/summaries/daily/{business_day}.md`**（**ファイル名 = 観測日**、翌朝生成でも前日の日付）と成否ログ **`YYYY-MM-DD.generation.json`**。GitHub Actions では **`--from-api`**（本番 `/api/summaries/daily-snapshots`）。`GITHUB_ACTIONS` で Fly-private `DATABASE_URL` が注入されていても `--from-api` と同様に HTTP で読める。

**環境変数:** `DATABASE_URL`（ローカル直読み時）、`OPENAI_API_KEY`（`--dry-run` でキーなしのときは JSON のみで可）、`OPENAI_SUMMARY_MODEL`（省略時 `gpt-4o-mini`）、CI の HTTP 読みでは `TREND_DASHBOARD_BASE_URL`。

**使用方法:**
```bash
python scripts/generate_ai_daily_summary.py --dry-run --business-day 2026-05-10
python scripts/generate_ai_daily_summary.py --write --force
python scripts/generate_ai_daily_summary.py --from-api --write --force
```

**注意:** 本番 DB 直結のため、リポジトリやログに接続文字列を出さないこと。CI では GitHub **Secrets** のみを使用。

詳細は `docs/summaries/README.md` を参照。

### generate_ai_weekly_summary.py
`docs/summaries/daily/{月〜日の business_day}.md`（その ISO 週の7日分、欠損可）だけを入力に OpenAI で週次＋ホットトピックを1ファイル生成する。日次ファイル名は観測日（[`docs/summaries/weekly/README.md`](../docs/summaries/weekly/README.md)）。DB・トレンド API は使わない。

**環境変数:** `OPENAI_API_KEY`（必須）、`OPENAI_SUMMARY_MODEL`（省略時 `gpt-4o-mini`）。

**使用方法:**
```bash
python scripts/generate_ai_weekly_summary.py --dry-run
python scripts/generate_ai_weekly_summary.py --write --force
python scripts/generate_ai_weekly_summary.py --weekly-for-date 2026-05-14 --write --force
```

詳細は `docs/summaries/README.md` を参照。

## 注意事項

- これらのスクリプトは開発・デバッグ用です
- 本番環境で実行する場合は、事前にデータベース接続情報を確認してください
- 環境変数（`.env`）が正しく設定されていることを確認してください

# Scripts

運用・CI・ローカルメンテ用のスクリプト。詳細なサマリー運用は [`docs/summaries/README.md`](../docs/summaries/README.md) を参照。

## CI / 本番パイプライン

| スクリプト | 役割 |
|-----------|------|
| `generate_ai_daily_summary.py` | 日次サマリー生成（GHA `ai-daily-summary.yml`） |
| `generate_ai_weekly_summary.py` | 週次サマリー生成（GHA `ai-weekly-summary.yml`） |
| `attach_daily_thumbs.py` | 日次サムネ生成・添付 |
| `publish_summaries_to_site.py` | 原稿・サムネを本番 API に upsert |
| `check_summary_already_published.py` | 既公開なら GHA をスキップ |
| `send_summary_dogfood_email.py` | dogfood メール送信 |
| `send_summary_paid_email.py` | 有料サマリーメール送信 |
| `purge_snapshot_retention.py` | スナップショット / サマリー保持期間の掃除（GHA `summary-retention-purge.yml`） |
| `record_deploy.py` | Fly `release_command` でデプロイ時刻を記録 |
| `refresh_trends_region.py` | スケジューラがリージョン refresh を subprocess 起動 |

```bash
# 日次（手元例）
python scripts/generate_ai_daily_summary.py --from-api --write --force --region jp
python scripts/attach_daily_thumbs.py
SUMMARY_UPSERT_TOKEN=... python scripts/publish_summaries_to_site.py

# 週次（手元例）
python scripts/generate_ai_weekly_summary.py --from-api --write --force --region jp
```

共有ロジック: `snapshot_rising.py`（日次/週次から import。直接実行しない）。

## リリース / 計測

| スクリプト | 役割 |
|-----------|------|
| `release.sh` | preflight（pytest・secret scan）／任意で commit・push・deploy |
| `run_lighthouse.sh` | Lighthouse 計測ラッパー（詳細は `docs/PERFORMANCE.md`） |
| `build_inter.py` | Inter 自前ホスト用 CSS/フォント生成 |
| `build_noto_sans_jp.py` | Noto Sans JP 自前ホスト用生成 |
| `build_fontawesome_subset.py` | Font Awesome サブセット CSS 生成 |

```bash
./scripts/release.sh
./scripts/release.sh --ship
./scripts/run_lighthouse.sh https://trends-dashboard.com/ mobile
```

## スナップショット運用（手動補完）

| スクリプト | 役割 |
|-----------|------|
| `inspect_scheduler_slots.py` | スロット有無の確認 |
| `backfill_snapshot_slot.py` | 指定 1 スロットをキャッシュから保存 |
| `backfill_missing_snapshot_slots.py` | 欠落スロットの一括補完 |

```bash
# Fly SSH 例
fly ssh console -a trends-dashboard -C \
  "cd /app && PYTHONPATH=/app python scripts/inspect_scheduler_slots.py --business-day 2026-06-20"
```

## キャッシュ確認 / ローカル開発

### check_cache.py
ローカル DB のキャッシュ件数確認。

```bash
python scripts/check_cache.py
```

### check_cache_remote.py
Fly.io 上（またはリモート `DATABASE_URL`）でのキャッシュ確認。今日 7 時（JST）更新の有無も見る。

```bash
fly ssh console -a trends-dashboard
python scripts/check_cache_remote.py
```

### update_book_trends.py
本トレンド全カテゴリを API から取得してキャッシュ更新。

```bash
python scripts/update_book_trends.py
# 本番: fly ssh console -a trends-dashboard → 同上
```

### bootstrap_dummy_cache.py
全カテゴリにダミーデータ（25件）をキャッシュ。ローカル UI 確認用（既存キャッシュを上書き）。

```bash
python scripts/bootstrap_dummy_cache.py
```

## サマリー下書き（任意）

本流は AI 生成パイプライン。空 Markdown をテンプレから用意したいときだけ使う。

```bash
python scripts/scaffold_summary_drafts.py --today
python scripts/scaffold_summary_drafts.py --daily 2026-05-11
python scripts/scaffold_summary_drafts.py --weekly-for-date 2026-05-11 --force
```

## 注意事項

- 本番 DB / Secrets を扱うスクリプトでは接続文字列をログやコミットに出さない
- GHA では GitHub Secrets、Fly では `fly secrets` を使う
- アセット系 `build_*.py` は生成物を `static/` に書く。再実行は依存更新時のみでよい

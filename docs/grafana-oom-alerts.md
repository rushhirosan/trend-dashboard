# Grafana / Fly ログ: OOM アラート設定

アプリ内 `memory_watchdog` は cgroup 使用率で **事前警告** する。カーネル OOM（SIGKILL）本体はプロセス内では捕捉できないため、**ログ監視を併用**する。

## Fly.io Logs → Grafana（推奨）

Fly ダッシュボードの **Logs** または Grafana 連携で以下をアラート条件にする。

### クエリ例（Loki / テキスト検索）

```
Out of memory
```

または

```
Killed process
```

```
oom-kill
```

```
anon-rss
```

### 推奨アラート

| 名前 | 条件 | 意味 |
|------|------|------|
| OOM killed | `Out of memory` または `Killed process` | カーネルがプロセスを強制終了 |
| Scheduler refresh OOM | 上記 + `refresh subprocess` または `gunicorn` | 定時取得中の OOM |

### 通知先

- Discord Webhook（運用チャンネル）
- 既存の `memory_watchdog` Discord と **役割分担**: watchdog=事前警告、Grafana=事後確定

## アプリ側（本番 fly.toml）

| 変数 | 値 | 説明 |
|------|-----|------|
| `DISCORD_MEMORY_PRESSURE_ALERT` | `true` | 逼迫時 Discord |
| `MEMORY_LIMIT_MB` | `1024` | cgroup 未取得時の fallback |
| `MEMORY_WATCHDOG_INTERVAL_SEC` | `15` | 監視間隔（旧 45s → 短縮） |
| `MEMORY_PRESSURE_WARN_RATIO` | `0.75` | 警告（1024MB で ~768MB） |
| `MEMORY_PRESSURE_CRITICAL_RATIO` | `0.88` | 危険（~1352MB） |
| `MEMORY_PRESSURE_ALERT_COOLDOWN_SEC` | `600` | 同一レベル再通知間隔 |

監視 API: `GET /api/alert/test` で `usage_mb` / `cgroup_usage_mb` / `usage_ratio` を確認。

## 定時スロット確認

```bash
fly ssh console -a trends-dashboard -C \
  "cd /app && PYTHONPATH=/app python scripts/inspect_scheduler_slots.py --business-day 2026-06-20"
```

欠損 backfill:

```bash
fly ssh console -a trends-dashboard -C \
  "cd /app && PYTHONPATH=/app python scripts/backfill_missing_snapshot_slots.py --days 3 --dry-run"
```

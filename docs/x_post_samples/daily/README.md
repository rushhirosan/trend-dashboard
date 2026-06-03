# 日次 X 文案（1日1ファイル）

`scripts/generate_daily_x_post_series.py --write` および GitHub Actions **Daily X post series** が、JST 当日向けに **`YYYY-MM-DD.md`** をここに出力します。型は [`../daily_guide.md`](../daily_guide.md) のテンプレート節と同じです。

**Discord:** workflow は `--discord` で JP/US 文案を送信（スケジューラ通知と同じ `DISCORD_WEBHOOK_URL`）。

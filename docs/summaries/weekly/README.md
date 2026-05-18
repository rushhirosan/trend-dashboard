# AI 週次サマリー — ISO 週1ファイル

[`generate_ai_weekly_summary.py`](../../scripts/generate_ai_weekly_summary.py) が、**日次サマリー Markdown だけ**を入力に `weekly/YYYY-Www.md`（週次＋週のホットトピック）を生成します。DB・トレンド API は使いません。

## ファイル名

| 形式 | 例 | 意味 |
|------|-----|------|
| `YYYY-Www.md` | `2026-W20.md` | **ISO 週**（月曜始まり）。対象はその週の月〜日（JST カレンダー） |

フロントマターの `week_range_jst`（例: `2026-05-12 〜 2026-05-18`）が、その週に含める **7 日分の観測日** です。

## 日次ファイルの読み方（重要）

週次は次のパスを **カレンダー上の月〜日、各1ファイル** として探します。

```
docs/summaries/daily/2026-05-12.md  … 月曜の business_day
…
docs/summaries/daily/2026-05-18.md  … 日曜の business_day
```

日次の `YYYY-MM-DD` は **観測日（business_day）** であり、発行日ではありません（日曜分は **翌週月曜 06:50 JST** 前後に `2026-05-18.md` として届く）。週次ジョブは **日曜分の日次がコミットされたあと** に走る想定です（[`docs/summaries/README.md`](../README.md) のタイムライン）。

欠けている日は `missing_daily_dates` に記録され、プロンプト上は「（ファイルなし）」として渡されます。

## 既定の対象週

- **引数なし**: JST の **直前に終了した ISO 週**（今週月曜の7日前が週の月曜）。
- **`--weekly-for-date YYYY-MM-DD`**: その日を含む ISO 週（`scaffold_summary_drafts.py --weekly-for-date` と同じ）。

## 自動化

- GitHub Actions: `.github/workflows/ai-weekly-summary.yml`（UTC 月曜 `15 23 * * 1` ≒ **翌 JST 火曜朝**）。日曜 `business_day` の日次（月曜 06:50 JST 生成）のあとを想定。

親ドキュメント: [`docs/summaries/README.md`](../README.md)

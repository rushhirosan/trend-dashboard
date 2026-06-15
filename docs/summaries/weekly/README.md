# AI 週次サマリー — ISO 週1ファイル

[`generate_ai_weekly_summary.py`](../../scripts/generate_ai_weekly_summary.py) が、**7日分の trend_daily_snapshots**（既定）を地域別（🇯🇵 日本 / 🇺🇸 アメリカ）に集計し、OpenAI で `weekly/YYYY-Www.md` を生成します。日次 Markdown は補助コンテキスト（欠損可）。

## 地域別の構成

週次レポートは **日本とアメリカを対称に** 扱います。

- **今週の流れ**: `flow_jp` / `flow_us` の2段落
- **急上昇・クロスソース**: 各地域ごとに最大3件ずつ（機械集計）
- **週次 rising**: 日次 top5 ではなく **資格あり候補を7日分すべて** 週次集計。`週次スコア = 出現日数×100 + 観測スロット数×5 + jump合計 + 複数ソース+25 + 系列重み` で top3 を選ぶ

米国ソースだけを混ぜて全体トップ5を取る旧方式は廃止しています。
末尾の「ソース一覧」「週のホットトピック」も廃止（急上昇・クロスソースにリンクと根拠があるため）。

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

- **引数なし**: JST の **直前に終了した ISO 週**（= **W1**: 月曜〜日曜）。W2 の月曜朝にジョブが走るとき、対象はその直前の月曜が週の始まり。
- **`--weekly-for-date YYYY-MM-DD`**: その日を含む ISO 週（`scaffold_summary_drafts.py --weekly-for-date` と同じ）。

## 自動化

- GitHub Actions: `.github/workflows/ai-weekly-summary.yml`（UTC 日曜 `30 22 * * 0` ≒ **JST 月曜 07:30**）。W1 日曜 `business_day` の日次（月曜 06:50 JST）のあと。原稿コミット後、配信目標はパターンAの **月曜 11:00 JST**（[`summary_pattern_a_phase1.md`](../../summary_pattern_a_phase1.md)）。

親ドキュメント: [`docs/summaries/README.md`](../README.md)

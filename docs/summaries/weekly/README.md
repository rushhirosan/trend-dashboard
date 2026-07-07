# AI 週次サマリー — ISO 週1ファイル

[`generate_ai_weekly_summary.py`](../../scripts/generate_ai_weekly_summary.py) が、**7日分の trend_daily_snapshots**（既定）を地域別（🇯🇵 日本 / 🇺🇸 アメリカ）に集計し、OpenAI で `weekly/YYYY-Www.md` を生成します。日次 Markdown は補助コンテキスト（欠損可）。

## 構成（1枚 PDF 向け）

週次レポートは **日本とアメリカを対称に** 扱います。

1. **今週の流れ** — `flow_jp` / `flow_us`（OpenAI）。正本は `weekly_category_digest`（カテゴリ別週次 top3 の集計）
2. **今週いちばん動いた話題** — 週内 jump 最大の1件。日別ベスト順位の連鎖のみ
3. **カテゴリ別 — 今週の top3** — 日次の `build_category_top3` を7日分集約（ニュース / 検索・動画 / テック・開発 / マーケット / エンタメ）

### カテゴリ digest（週次集計）

各日 × 地域のスナップショットから日次カテゴリ top3 を取り、ラベル単位で週次スコア化します。

`週次スコア = 出現日数×10 + 複数ソース+15 + 系列重み`

複数ソースで重なった話題は、カテゴリ内の `複数ソース` バッジとして表示します（独立セクションは廃止）。

### 急上昇（各地域1件）

日次 rising 候補を7日分集約し、jump 偏重の週次スコアで各地域 top1 のみ表示します。**週内の動き**（日別ベスト順位の連鎖・矢印なし）のみ付けます。

### カテゴリ別 top3（機械生成）

日次カテゴリ top3 候補を週次プール化し、**具体 label・リンク付き**で機械表示（日次 digest と同形式）。

**カテゴリ混在は禁止**: 各区分は `categorize_series_key`（ダッシュボードタブ準拠）でそのカテゴリに属する series のみ（週次でも再検証）。
検索・動画だけ日次より狭く **Google Trends / YouTube / Wikipedia のみ**。

選定時の重複抑制:
- **ニュース**: 豪雨など同一トピックの別見出しは1件に集約
- **検索・動画**: **Google Trends / YouTube / Wikipedia のみ**（週次 digest。はてな・Twitch 等は含めない）
- **マーケット等**: まずソースごとに1件ずつ確保し、不足分はスコア順で埋める（他ソースがあれば同一ソース2件も可）
- **急上昇**: 日本1位と同一ラベルの話題は米国でスキップし次点を表示
各カテゴリ最大3件。根拠行（`>` 始まり）は日別ベスト順位の連鎖。

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

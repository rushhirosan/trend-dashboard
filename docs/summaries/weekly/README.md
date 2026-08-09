[`generate_ai_weekly_summary.py`](../../scripts/generate_ai_weekly_summary.py) が、**7日分の trend_daily_snapshots**（既定）を **`--region` ごとに**集計し、OpenAI で週次サマリーを生成します。

| `--region` | 出力 | 言語 | 対象ソース |
|------------|------|------|------------|
| `jp`（既定） | `weekly/YYYY-Www.md` | 日本語 | 日本ページ向け系列のみ |
| `us` | `weekly/us/YYYY-Www.md` | 英語 | アメリカページ向け系列のみ |

日次 Markdown は同地域のファイルを補助コンテキストとして読む（欠損可）。

## 構成（1枚向け・単一地域）

1. **今週の流れ / Week in review** — OpenAI（週としての1本線。日次の列挙にしない）
2. **今週いちばん動いた話題 / Biggest movers** — 週内で実質ジャンプしたものだけ（横ばい除外）
3. **週のホットトピック / Hot topics** — 厳選・上限5（OpenAI）
4. **来週に残る論点 / What to watch next week** — 2〜3点（OpenAI）
5. **カテゴリ別 — 今週の top3 / Category top3** — 日次カテゴリ top3 の週次集約（機械）

> 以前は1ファイルに日本・アメリカを対称配置していましたが、**日本語ページ／USページで原稿を分けました**。

### カテゴリ digest（週次集計）

各日のスナップショット（対象地域のみ）から日次カテゴリ top3 を取り、ラベル単位で週次スコア化します。

`週次スコア = 出現日数×10 + 複数ソース+15 + 系列重み`

複数ソースで重なった話題は、カテゴリ内の `複数ソース` バッジとして表示します（独立セクションは廃止）。

### 急上昇（地域1件）

日次 rising 候補を7日分集約し、jump 偏重の週次スコアで top1 のみ表示します。

### カテゴリ別 top3（機械生成）

日次カテゴリ top3 候補を週次プール化し、**具体 label・リンク付き**で機械表示（日次 digest と同形式）。

**カテゴリ混在は禁止**: 各区分は `categorize_series_key`（ダッシュボードタブ準拠）でそのカテゴリに属する series のみ（週次でも再検証）。
検索・動画だけ日次より狭く **Google Trends / YouTube / Wikipedia のみ**。

選定時の重複抑制:
- **ニュース**: 豪雨など同一トピックの別見出しは1件に集約
- **検索・動画**: **Google Trends / YouTube / Wikipedia のみ**（週次 digest。はてな・Twitch 等は含めない）
- **マーケット等**: まずソースごとに1件ずつ確保し、不足分はスコア順で埋める（他ソースがあれば同一ソース2件も可）
各カテゴリ最大3件。根拠行（`>` 始まり）は日別ベスト順位の連鎖。

日次と同様、Medium / OpenAlex / GlobeNewswire / eBay / Bluesky / **Twitch（同時視聴）** / 行政データは digest 対象外（ダッシュボード表示は別）。

## ファイル名

| 形式 | 例 | 意味 |
|------|-----|------|
| `YYYY-Www.md` | `2026-W20.md` | **ISO 週**（月曜始まり）。対象はその週の月〜日（JST カレンダー） |

フロントマターの `week_range_jst`（例: `2026-05-12 〜 2026-05-18`）が、その週に含める **7 日分の観測日** です。`region` フィールドで jp/us を明示します。

## 日次ファイルの読み方（重要）

週次は同地域の日次を **カレンダー上の月〜日、各1ファイル** として探します。

```
# JP
docs/summaries/daily/2026-05-12.md  … 月曜の business_day
…
# US
docs/summaries/daily/us/2026-05-12.md
```

日次の `YYYY-MM-DD` は **観測日（business_day）** であり、発行日ではありません（日曜分は **翌週月曜 06:50 JST** 前後に届く）。週次ジョブは **日曜分の日次がコミットされたあと** に走る想定です。

欠けている日は `missing_daily_dates` に記録され、プロンプト上は「（ファイルなし）」として渡されます。

## 既定の対象週

- **引数なし**: JST の **直前に終了した ISO 週**（= **W1**: 月曜〜日曜）。W2 の月曜朝にジョブが走るとき、対象はその直前の月曜が週の始まり。
- **`--weekly-for-date YYYY-MM-DD`**: その日を含む ISO 週。
- **`--region jp|us`**: 生成対象ページ（既定 jp）。

## 自動化

- GitHub Actions: `.github/workflows/ai-weekly-summary.yml`（UTC 日曜 `30 22 * * 0` ≒ **JST 月曜 07:30**）。同一ジョブで jp → us を直列生成。

親ドキュメント: [`docs/summaries/README.md`](../README.md)

# AI 日次サマリー — 1日1組のファイル

[`generate_ai_daily_summary.py`](../../scripts/generate_ai_daily_summary.py) が（`--write` 時）、常に次の **2つを同じ `business_day`** で扱います。

| ファイル | 内容 |
|----------|------|
| `YYYY-MM-DD.md` | OpenAI で生成した Markdown（成功時のみ上書き。**`generator: openai`** がフロントマターにあるのが AI 生成の目印）。構成は **一行結論・見どころ（AI、不整合時は機械補完）→ 急上昇3つ（機械+補足）→ 複数ソース重なり（機械・厳密一致）→ カテゴリ別トップ3（機械+区分1文）**（観測日＝ファイル名、読者は通常翌朝に受け取る）。`.generation.json` の `one_liner_source` / `spotlights_filled` で補完の有無を確認できる |
| `YYYY-MM-DD.generation.json` | その回の **成否ログ**（成功なら `ok: true` と行数・モデル、失敗なら `ok: false` と `error` / `phase`） |

## ファイル名の日付（観測日 = `business_day`）

**`YYYY-MM-DD` は「届いた日」ではなく、その日のトレンドをまとめた観測日（`business_day`）** です。

| 例 | 意味 |
|----|------|
| `2026-05-18.md` | **5/18 一日分**のトレンドサマリー（07/13/19/01 スナップショット） |
| `generated_at: 2026-05-19 07:43 JST` | **5/19 朝**に生成・コミットされた（正常） |

- フロントマターの `business_day` / `summary_date` とファイル名は **同じ日付** に揃える。
- 見出し `# 日次サマリー — YYYY-MM-DD` と **対象** 行も同じ日付にする（モデルがずれたら `--force` で再生成）。
- 入力データは `trend_daily_snapshots` の **`business_day`**（[`docs/summaries/README.md`](../README.md) のタイムライン参照）。

**X 投稿案**（`docs/x_post_samples/daily/`）— **使用していない（2026-07 停止）**。日次サマリーと同じ `YYYY-MM-DD` の命名規則だったが、自動生成・投稿は行わない。

## 運用

- **スキャフォルドだけ**の `.md`（テンプレ文言のまま）は `generator` 行が無く、`.generation.json` も無いことが多いです。差分はここで判別できます。使わないプレースホルダは **削除してよい**（あとから `generate_ai_daily_summary.py --write --force --business-day …` で再生成できる）。
- GitHub Actions **AI daily summary**（JST **06:50** 前後）は、既定で **JST 昨日** を `business_day` にして `docs/summaries/daily/` を更新します。失敗時も `.generation.json` をコミットしてからジョブを失敗扱いにします。

親ドキュメント: [`docs/summaries/README.md`](../README.md)

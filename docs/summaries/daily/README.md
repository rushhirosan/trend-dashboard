# AI 日次サマリー — 1日1組のファイル

[`generate_ai_daily_summary.py`](../../scripts/generate_ai_daily_summary.py) が（`--write` 時）、常に次の **2つを同じ `business_day`** で扱います。

| ファイル | 内容 |
|----------|------|
| `YYYY-MM-DD.md` | OpenAI で生成した Markdown（成功時のみ上書き。**`generator: openai`** がフロントマターにあるのが AI 生成の目印） |
| `YYYY-MM-DD.generation.json` | その回の **成否ログ**（成功なら `ok: true` と行数・モデル、失敗なら `ok: false` と `error` / `phase`） |

- **スキャフォルドだけ**の `.md`（テンプレ文言のまま）は `generator` 行が無く、`.generation.json` も無いことが多いです。差分はここで判別できます。使わないプレースホルダは **削除してよい**（あとから `generate_ai_daily_summary.py --write --force --business-day …` で再生成できる）。
- GitHub Actions **AI daily summary** は生成ステップ後に **`docs/summaries/daily/` 以下をまとめてコミット**し、スクリプトが失敗しても `.generation.json` が残れば記録されます。

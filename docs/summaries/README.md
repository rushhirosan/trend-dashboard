# サマリー原稿（リポジトリ保管・配信前レビュー）

パターンA・フェーズ1で作成する **日次サマリー／週次サマリー／週のホットトピック** を Markdown で毎コミットしていく場所。**サイトには公開しない**（静的ページやルートは未接続）。

**X ポストサンプル**（`docs/x_post_samples/`）と同じ考え方:

1. **ここに下書きを日々積む**（人が書く／AIが叩いた案を貼る、どちらでもよい）
2. **レビューで品質・リンク・事実関係を確認**（フロントマターの `status` で区別）
3. **問題なければ配信パイプラインに載せる**（メール・X・有料枠などは別実装。原稿の正本はこのディレクトリ）

運用の約束・タイムボックス・チェックリストの詳細は [`summary_pattern_a_phase1.md`](../summary_pattern_a_phase1.md) を正とする。

---

## ディレクトリとファイル

| パス | 内容 |
|------|------|
| `daily_template.md` | 日次のひな形（フロントマター付き） |
| `weekly_hot_bundle_template.md` | 週次＋ホットを1ファイルにまとめるひな形 |
| `daily/` | 日次サマリー（**1日1組**・観測日ファイル名）。[`daily/README.md`](daily/README.md) |
| `weekly/` | 週次サマリーと週のホットトピックを **1ファイルにまとめる**。[`weekly/README.md`](weekly/README.md) |

---

## 命名規則

| 種別 | 形式 | 日付の意味 |
|------|------|------------|
| 日次 | `daily/YYYY-MM-DD.md` | **観測日（`business_day`）** — その JST 暦日のトレンドをまとめた1本。ファイル名は **届いた日ではない**（詳細は [`daily/README.md`](daily/README.md)） |
| 日次（成否ログ） | `daily/YYYY-MM-DD.generation.json` | 上と同じ `business_day` |
| 週次（＋ホット） | `weekly/YYYY-Www.md` | **ISO 週**（月曜〜日曜）。入力はその7日分の日次ファイル名（観測日） |

日付の解釈で迷ったら、各ファイル先頭のフロントマター（`business_day` / `week_range_jst`）と見出しの「対象」「対象週」を正とする。

### 日次サマリーのタイムライン（JST）

| 観測日（`business_day`・ファイル名） | スナップショット | 日次サマリーが届く目安 |
|--------------------------------------|------------------|-------------------------|
| 5/18（日） | 5/18 の 07 / 13 / 19、翌暦日 01 で前日を閉じる | **5/19 06:50** 前後（Actions **AI daily summary**） |
| 5/19（月） | 同上 | **5/20 06:50** 前後 |

- スクリプト既定: `generate_ai_daily_summary.py` は **JST の昨日** を `business_day` にする（`--business-day` で上書き可）。
- **夜の X 投稿案**（`docs/x_post_samples/daily/YYYY-MM-DD.md`）は **その暦日の 20:10 前後** に同じ日付で出る。サマリーと **同じ `YYYY-MM-DD` なら同じ「一日」** の話題（サマリーは翌朝）。

### 週次のタイムライン（JST）

**W1（先週）の月曜〜日曜**の日次をまとめ、**W2（翌週）の月曜**に週次を生成する（パターンAの配信目標 11:00 より前に原稿をコミット）。

例: W20 = 月 **5/11** 〜 日 **5/17** をまとめ、**5/18（月）** に `weekly/2026-W20.md` を生成:

1. 日曜観測日 `2026-05-17.md` が **月曜 5/18 06:50** 前後（**AI daily summary**）に揃う。
2. **月曜 5/18 07:30** 前後に **AI weekly summary** が `weekly/2026-W20.md` を生成・コミット。
3. 人のレビュー・配信は [`summary_pattern_a_phase1.md`](../summary_pattern_a_phase1.md) のとおり **月曜 11:00 JST**（遅延上限 12:00）を目標。

詳細: [`weekly/README.md`](weekly/README.md)

---

## 週次ファイルの中身

`weekly/YYYY-Www.md` の **1ファイル**に次の両方を含める:

1. 週次サマリー（パターンAの「週次サマリー」セクション）
2. 週のホットトピック（同「週のホットトピック」セクション）

見出しの分け方の例は `weekly_hot_bundle_template.md` を参照。

---

## レビューと配信のゲート（フェーズ1）

| `status` | 意味 |
|----------|------|
| `draft` | 推敲・事実確認中。**配信に使わない** |
| `approved` | レビュー済み。**配信してよい正本**として扱う |

- レビューした人はフロントマターの `reviewer` / `reviewed_at` を埋める（任意だが推奨）
- 配信開始の判断はプロダクト側の合意で行う（この README だけでは自動化しない）

品質の観点は `summary_pattern_a_phase1.md` のチェックリストをそのまま使える。

---

## 下書きファイルの作成（スキャフォルド）

テンプレから空の Markdown を生成する:

```bash
# JST の今日の日付で日次だけ
python scripts/scaffold_summary_drafts.py --today

# 指定日の日次
python scripts/scaffold_summary_drafts.py --daily 2026-05-11

# その日が属する ISO 週の週次＋ホット用ファイル（weekly/2026-W19.md など）
python scripts/scaffold_summary_drafts.py --weekly-for-date 2026-05-11

# まとめて（上書きしたいときは --force）
python scripts/scaffold_summary_drafts.py --today --weekly-for-date 2026-05-11
```

`--weekly-for-date` は、その**日付が属する ISO 週**のファイルを作る。パターンAの「先週」まとめを月曜に書くときは、**先週のカレンダー上の日**を1つ渡す（例: 先週の月曜）。

既に同名ファイルがある場合は **上書きしない**（`skip (exists): ...`）。上書きする場合のみ `--force`。

---

## AI 日次サマリー（DB スナップショット → OpenAI）

`scripts/generate_ai_daily_summary.py` が `trend_daily_snapshots` の **前日 `business_day`** × スロット **07 → 13 → 19 → 01**（`01` は翌暦日 1 時ジョブで前日を閉じる）を読み、`gpt-4o-mini`（`OPENAI_SUMMARY_MODEL` で変更可）で **`docs/summaries/daily/{business_day}.md`** を生成する（**ファイル名 = 観測日**、生成実行日ではない）。

**`--write` 時は同じディレクトリに `YYYY-MM-DD.generation.json` を必ず書き**（成功・失敗・キー欠如・スナップショット空・OpenAI エラー）— X 投稿の `daily/*.md` と同様に、**日付ごとに結果を追いやすくする**ため。

- **JST 6:50 前後**に動かす想定（7 時一括取得より前で、前日の `01` スロットが揃ったあと）。GitHub Actions: `.github/workflows/ai-daily-summary.yml`（UTC `50 21 * * *`）。失敗時も `.generation.json` をコミットしてからジョブを失敗扱いにする。
- **Secrets（GHA）**: `OPENAI_API_KEY`（必須）。`DATABASE_URL` は不要（`--from-api` で本番 `/api/summaries/daily-snapshots` を使用）。
- **手元**: `.env` に `DATABASE_URL` と `OPENAI_API_KEY` を設定（DB 直読み）、または `--from-api`。

```bash
# JSON ペイロードだけ（API 課金なし）。DB があれば自動、無ければ --from-api
python scripts/generate_ai_daily_summary.py --dry-run --business-day 2026-05-10
python scripts/generate_ai_daily_summary.py --dry-run --from-api --business-day 2026-05-10

# 標準出力へ全文（課金あり）
python scripts/generate_ai_daily_summary.py --business-day 2026-05-10

# ファイルへ（`YYYY-MM-DD.md` と `YYYY-MM-DD.generation.json`、既存 .md は --force）
python scripts/generate_ai_daily_summary.py --write --force --business-day 2026-05-10

# CI 相当
python scripts/generate_ai_daily_summary.py --from-api --write --force
```

生成ファイルはフロントマターに `generator: openai` を付ける。本文は **一行結論・見どころ（AI JSON）→ 急上昇3つ（機械+AI補足）→ 複数ソース重なり（機械・厳密一致）→ カテゴリ別トップ3（機械+区分1文）**。成否は **`daily/README.md`** のとおり **`*.generation.json`** で確認。**レビュー後に `approved` にするまで配信に使わない。**

---

## AI 週次サマリー（日次 Markdown ×7 → OpenAI）

`scripts/generate_ai_weekly_summary.py` は **対象週の月〜日それぞれ** `docs/summaries/daily/{YYYY-MM-DD}.md` を探して最大7件読むだけで、DB や公開トレンド API・スナップショットには触れない。日次の `YYYY-MM-DD` は **観測日（business_day）**（[`weekly/README.md`](weekly/README.md)）。`gpt-4o-mini`（`OPENAI_SUMMARY_MODEL` で変更可）で `docs/summaries/weekly/YYYY-Www.md`（週次＋週のホットトピックを1ファイル）を生成する。

- **既定の対象週**: JST の **直前に終了した ISO 週**（月曜始まり7日分の観測日ファイルを期待）。
- **`--weekly-for-date YYYY-MM-DD`**: その日を含む ISO 週をまとめる（`scaffold_summary_drafts.py --weekly-for-date` と同じ週の取り方）。
- **Secrets（GHA）**: `OPENAI_API_KEY` のみ（`DATABASE_URL` は不要）。GitHub Actions: `.github/workflows/ai-weekly-summary.yml`（タイムラインは上記「週次のタイムライン」）。
- **手元**: `.env` に `OPENAI_API_KEY`。`--dry-run` でキーなしのときは読み込みマニフェストとロールアップ先頭のみ（課金なし）。

```bash
# マニフェストのみ（API 課金なし）
python scripts/generate_ai_weekly_summary.py --dry-run --weekly-for-date 2026-05-14

# 標準出力へ全文（課金あり）
python scripts/generate_ai_weekly_summary.py --weekly-for-date 2026-05-14

# ファイルへ（既存は --force で上書き）
python scripts/generate_ai_weekly_summary.py --write --force --weekly-for-date 2026-05-14
```

生成ファイルはフロントマターに `generator: openai` と欠損日一覧を付ける。**レビュー後に `approved` にするまで配信に使わない。**

---

## Git

- コミットメッセージ例: `docs(summaries): add daily 2026-05-06` / `docs(summaries): weekly 2026-W19` / `docs(summaries): approve weekly 2026-W19`
- 個人情報・社外秘を本文に書かない（リンクは公開 URL のみ推奨）

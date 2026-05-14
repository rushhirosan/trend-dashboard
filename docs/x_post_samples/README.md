# X（Twitter）投稿サンプル

Trend Dashboard 向けの **1日1ツイート（20時）** と **週1振り返り（1ツイート）** のテンプレートと例文です。  
**あくまでサンプル**です。実際の投稿前にダッシュの内容と更新時刻に合わせて差し替えてください。

---

## 運用メモ（プロダクト仕様との整合）

- トレンド一括取得は **1 / 7 / 13 / 19 時（JST）** のスケジューラ実行がベース。
- **20時投稿**なら、本文の「反映」は例として **「当日 13:00・19:00 更新を中心に反映」** のように書くと誤解が少ない。
- **JP / US を同じ JST 20:00** に出す運用にすると、US 向け英語ポストは現地ではだいたい**朝**になる。**US 投稿の冒頭（または返信）にその前提**を書いておくと時差の誤解が減る（`daily_template.md` の「同時刻運用」参照）。
- **日次の本文投入:** `DATABASE_URL` ありで `scripts/generate_daily_x_post_series.py --write`（DB の `trend_daily_snapshots` 07/13/19）、または GitHub Actions `Daily X post series`（JST 20:10 前後、`--from-api` で本番の `/api/summaries/daily-snapshots` と同じ行を読む）で `daily_series_from_2026-05-09.md` を更新する。DB も HTTP も無いときだけ、スクリプトを引数なしで叩くとレガシーなソース別 `/api/*` 経路になる。

---

## ファイル一覧

| ファイル | 内容 |
|----------|------|
| `daily_template.md` | 毎日20時用テンプレ + **同時刻運用（JP+US）** + 埋め例 + 「今日の3つ」+ 「今日の5つ」（④Tech⑤エンタメ） |
| `weekly_template.md` | 週1振り返り用テンプレート + 埋め例 |
| `samples_2026-05-07.md` | **2026-05-07** 初回投稿向けのサンプル文案（本番APIキャッシュを参照して作成・更新） |
| `samples_2026-05-08.md` | **2026-05-08** 20時向け・カテゴリ別ハイライト全文、スレッド／1ツイート案、**今日の5つ（JP/US・①〜③+④Tech+⑤エンタメ）** 例（`GENERATED_AT_UTC` を冒頭に記載） |
| `daily_series_from_2026-05-09.md` | **2026-05-09 〜 05-22** の日別ツイート案（`scripts/generate_daily_x_post_series.py` で DB または `/api/summaries/daily-snapshots` から①〜⑤を自動投入可） |

サマリー原稿（配信前レビュー用）— 日次／週次／週のホットトピックをリポジトリに積む運用は、X サンプルと同様の流れで [`docs/summaries/README.md`](../summaries/README.md) を参照（下書き生成: `scripts/scaffold_summary_drafts.py`）。

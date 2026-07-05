# TODO — 急上昇3つ × 一覧 URL の UX

> **保留（2026-07）:** Daily X post series 停止に伴い **本 TODO は着手しない**。X / Discord 文案の自動運用は使用していない。

## 課題

Discord / X 文案の末尾:

```
一覧: https://trends-dashboard.fly.dev/
```

を踏むと **ダッシュボード TOP** に着くが、**その日の急上昇3つだけ** が並んだカードやセクションがない。  
投稿で選んだ ①②③ をダッシュ上でたどるのに時間がかかり、UX が噛み合っていない。

文案例:

```
【2026-06-08】今日の急上昇3つ（JP）
① なぜ人は重圧に…（ニュース）
② 推薦システムの…（IT）
③ TypeScript拡張…（IT）
一覧: https://trends-dashboard.fly.dev/
```

## やらないこと（決定済み）

- **`/` / `/us` のヘッダー領域に「急上昇3つ」カードを足す** — ヘッダーを広げたくないため revert 済み（`#rising-today` 案）

## 方針: ダッシュボード本体は触らず、導線を分ける

| ユーザー intent | 現状 | あるべき |
|-----------------|------|----------|
| X にそのまま貼る | Discord 長押しコピー | 280 字以内・記事 URL 行なし（md 同型） |
| 3 件を**読む** | 一覧 → 全ソースダッシュ | **記事 URL** へ直接（Discord 側） |
| 全体を**眺める** | 同上 | ルート `/` または別 URL で明示 |

---

## Phase 1（小さく・優先）— Discord 文案だけ

**ダッシュボード変更なし。**

1. **Discord を 2 役割に分ける**
   - **メッセージ A:** X コピー用（`build_x_post_blocks_for_discord_copy` 相当 — 280 字・記事 URL 行なし）
   - **メッセージ B:** 読む用 — ①②③ 各行 + **記事 URL**（`include_article_links=True`、文字数制限なし）
   - 既存: ヘッダー Embed + US 返信

2. **「一覧」の期待値を直す**
   - 文案または Discord ヘッダーで「全ソースのダッシュボード」と明記
   - 必要ならラベルを `全ソース:` / `Dashboard:` に変更（X 280 字内で収まる範囲）

3. **リンクプレビュー**
   - 記事 URL 行がある Discord メッセージには `flags: SUPPRESS_EMBEDS`（記事カード乱立防止）

4. **触るファイル（目安）**
   - `scripts/generate_daily_x_post_series.py` — `build_x_post_blocks_for_discord_copy`、Discord 分岐
   - `services/daily_x_post_notify.py` — 同上
   - `scripts/daily_x_post_discord.py` — 5 通目（リンク用）または 2 通構成の整理
   - `tests/test_*_daily_x_post_*`

---

## Phase 2（必要なら）— 専用ランディング

**`/` のヘッダーは触らない。新規ルートのみ。**

- 例: `GET /rising/2026-06-08`（JP）、`/us/rising/2026-06-08`（US）
- 同じ選定（`snapshot_rising` + `pick_rising_topics`）で 3 件 + 記事リンク + 「ダッシュボード全体へ」
- X / Discord の `一覧:` をこの URL に差し替え検討

---

## やらない方がよい案

- **`/#source-zenn` だけの deep link** — タブ切替なしでは見つけにくい（`app.js` の「もっと見る」は `data-target-tab` 前提）
- **GitHub md を一覧先にする** — モバイル Discord → GitHub は重い

---

## 関連

- 選定ロジック: `scripts/snapshot_rising.py`、`pick_rising_topics`（`generate_daily_x_post_series.py`）
- Discord 送信: `scripts/daily_x_post_discord.py`、`services/daily_x_post_notify.py`
- 運用ガイド: [`../daily_guide.md`](../daily_guide.md)

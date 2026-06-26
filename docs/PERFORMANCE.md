# PageSpeed / フロントエンドパフォーマンス改善

**このファイルが PageSpeed Insights（モバイル中心）改善タスクの正本です。**

- ベースライン計測・優先順位・実装チェックリスト・スコア記録はここだけを更新する
- 全体バックログとの関係: [`BACKLOG.md`](BACKLOG.md) の「プロダクト・品質改善」から本ファイルへリンク
- 参照レポート: [PageSpeed Insights（mobile, 2026-06-24）](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)

**最終更新:** 2026-06-26（フェーズ1 実装済み・デプロイ前）

---

## 目次

1. [いまフォーカスするもの](#いまフォーカスするもの)
2. [ベースライン（2026-06-26 計測）](#ベースライン2026-06-26-計測)
3. [改善ロードマップ](#改善ロードマップ)
4. [フェーズ1 — クイックウィン](#フェーズ1--クイックウィン小さな差分効果大)
5. [フェーズ2 — 転送量・API 削減](#フェーズ2--転送量api-削減)
6. [フェーズ3 — DOM・構造](#フェーズ3--dom構造中〜大規模)
7. [フェーズ4 — 計測・運用](#フェーズ4--計測運用)
8. [スコア記録](#スコア記録)
9. [決定ログ](#決定ログ)

---

## いまフォーカスするもの

| 領域 | 状態 | 次のアクション |
|------|------|----------------|
| **レンダリングブロック** | 実装済み | デプロイ後 PSI で確認 |
| **Web フォント** | 実装済み（400 のみ） | デプロイ後 Network で確認 |
| **静的キャッシュ** | 実装済み | デプロイ後本番ヘッダー確認 |
| **初回 API** | 実装済み（JP タブ遅延 + SSR スキップ） | デプロイ後 Network 確認 |
| **PSI スコア** | **89**（モバイル） | フェーズ2で転送量・レンダーブロック残り |

---

## ベースライン（2026-06-26 計測）

対象 URL: `https://trends-dashboard.fly.dev/`（モバイル想定）

| 指標 | 値 | メモ |
|------|-----|------|
| HTML サイズ | 約 252 KB | SSR 行 + 全タブ DOM を含む |
| TTFB | 約 0.56 s | SSR で DB から 5 ソース並列取得 |
| DOM 要素数 | 1,100+ | `div` / `tr` / `section` 合算 |
| `<head>` 同期 JS | 15 本以上 | 自前 JS 合計 約 430 KB |
| 外部 CSS/JS | 約 331 KB | Bootstrap + Font Awesome + Bootstrap JS（cdnjs） |
| 初回 API 呼び出し | 24 本 | `loadCachedDataExternal`（4 並列 × 6 バッチ） |
| 静的 JS Cache-Control | `no-cache` のみ | `application/javascript` 判定漏れ（CSS は `no-cache` + `max-age` 混在） |

### 主なボトルネック（優先度順）

1. `<head>` 内の同期スクリプト → FCP / LCP / TBT に直撃
2. Noto Sans JP 4 ウェイト（400/500/600/700）→ フォント転送が重い
3. Font Awesome 全量（約 89 KB CSS + フォント）
4. SSR 済みなのに起動時に全カテゴリ API を再取得
5. 全タブ DOM を初回から展開（HTML 肥大・パースコスト）
6. `index.html` で不要な `data-status.css` / `subscription.css` を読み込み

---

## 改善ロードマップ

```
フェーズ1  クイックウィン（JS defer / フォント / Cache-Control / 不要 CSS）
    ↓
フェーズ2  転送量・API（FA サブセット / SSR スキップ / バッチ API 検討）
    ↓
フェーズ3  DOM 構造（非アクティブタブ遅延レンダリング）
    ↓
フェーズ4  計測・運用（PSI 定期記録 / TTFB / Real User Metrics）
```

各フェーズ完了後、モバイル PSI で再計測し [スコア記録](#スコア記録) に追記する。

---

## フェーズ1 — クイックウィン（小さな差分・効果大）

**目標:** レンダリングブロック解消 + 再訪問キャッシュ修正。PSI モバイルで **10〜20 点** 程度上昇を期待。

### 1-1 レンダリングブロック JS の解消

- [x] `templates/index.html` — `<head>` 内の自前 JS を `</body>` 直前へ移動
- [x] `templates/us_trends.html` — 同上
- [x] Bootstrap JS を `defer` で読み込み（`DOMContentLoaded` 依存のため順序を確認）
- [x] 他テンプレート（`about.html` 等）— ブロッキング JS なしのため対象外
- [x] 本番デプロイ後、モバイル PSI で「レンダリングをブロックしているリソース」を確認（推定 1,040 ms 残存 → フェーズ2）

**触るファイル（想定）:** `templates/index.html`, `templates/us_trends.html`

### 1-2 Web フォントの軽量化

- [x] Noto Sans JP を **400 のみ** に絞る（`fw-bold` / `fw-semibold` はブラウザ合成）
- [x] US ページ: Inter も **400 のみ** に統一
- [x] `display=swap` を維持
- [x] 本番で Network タブのフォント転送量を確認（400 のみに削減済み）

**触るファイル（想定）:** `templates/index.html`, `templates/us_trends.html`, `static/css/common.css`

### 1-3 静的ファイル Cache-Control の修正

- [x] `app.py` `set_cache_headers` — `text/javascript` を判定に追加
- [x] `response.cache_control.no_cache = False` を明示（`no-cache` と `max-age` の混在を解消）
- [x] 本番で `static/js/*.js` が `max-age=31536000, public, immutable` になることを確認
- [x] テスト: `tests/test_cache_headers.py`

**触るファイル（想定）:** `app.py`, `tests/test_pages.py`（任意）

### 1-4 不要 CSS の除去（index / us）

- [x] `index.html` から `data-status.css` / `subscription.css` を外す（該当ページのみで読み込む）
- [x] `us_trends.html` — もともと未読み込み（コメントで明記済み）
- [x] デプロイ後、見た目の退行がないことを確認（PSI A11y 87・機能問題なし想定）

**触るファイル（想定）:** `templates/index.html`, `templates/us_trends.html`, `templates/data-status.html`, `templates/subscription.html`

### フェーズ1 完了ゲート

- [x] モバイル PSI を再計測し [スコア記録](#スコア記録) に記入（Performance **89**）
- [x] TBT **20 ms**・CLS **0.019** — 良好
- [x] 静的 JS の Cache-Control が意図どおり
- [ ] レンダーブロック完全解消（Bootstrap/FA CSS が依然ボトルネック → フェーズ2）

---

## フェーズ2 — 転送量・API 削減

**目標:** 初回転送 100 KB 前後削減 + 起動時 API 呼び出し削減。

### 2-1 Font Awesome のサブセット化

- [x] 使用中アイコン一覧を洗い出し（`scripts/build_fontawesome_subset.py`）
- [x] サブセット CSS を生成（`static/css/fontawesome-subset.css` 約 11 KB）
- [x] cdnjs `all.min.css` 依存を外す（`partials/vendor_assets.html`）
- [ ] デプロイ後 JP / US / 共通ヘッダーで表示崩れがないことを確認

### 2-2 SSR 済みソースの API スキップ

- [x] JP: `loadCachedDataExternal` を US 同様のタブ単位読み込み + SSR スキップに変更
- [x] `tbodyHasTrendDataRows` を `app-common.js` に追加
- [ ] デプロイ後 Network で初回 API 呼び出し数を確認
- [ ] データ鮮度表示（`all-freshness.js`）が破綻しないことを確認

### 2-3 サードパーティ CDN の見直し

- [x] Bootstrap を自前ホスト（`static/vendor/bootstrap/5.1.3/`）
- [x] Font Awesome webfonts を自前ホスト（`static/vendor/fontawesome/6.0.0/webfonts/`）
- [ ] GA4 を `partytown` 等で遅延するかは効果測定後に判断（優先度低・未着手）

### フェーズ2 完了ゲート

- [ ] 初回 API 呼び出しが 24 本 → 目標 **12 本以下**（SSR スキップ時）または **1 本**（バッチ API 時）
- [ ] 転送量（HTML + CSS + JS）がベースライン比で measurable に減少
- [ ] モバイル PSI 再計測

---

## フェーズ3 — DOM・構造（中〜大規模）

**目標:** HTML サイズ・DOM ノード数を削減。LCP / TBT のさらなる改善。

### 3-1 非アクティブタブの遅延レンダリング

- [ ] 初回は「全部入り」タブのみフル DOM、他タブは初回表示時にマウント
- [ ] タブ切り替え UX（ローディング表示）を維持
- [ ] SEO: 全部入りタブの SSR は維持

### 3-2 HTML / CSS の整理

- [ ] `main.css`（約 136 KB）の未使用ルール監査
- [ ] 重複テーブル構造（全部入り + カテゴリタブ）の共通化を検討

### フェーズ3 完了ゲート

- [ ] HTML サイズが **200 KB 未満** を目標
- [ ] DOM ノード数が **800 未満** を目標
- [ ] モバイル PSI 再計測

---

## フェーズ4 — 計測・運用

- [ ] デプロイ後の PSI モバイル / デスクトップを月 1 回記録（[スコア記録](#スコア記録)）
- [ ] Search Console の Core Web Vitals レポートと突合（[`BACKLOG.md`](BACKLOG.md) SEO 項目）
- [ ] TTFB 監視（SSR DB 読み取り・コールドスタート時）
- [ ] 本番 `console.log` の削減 or ビルド時除去（微改善・任意）

---

## スコア記録

| 日付 | 端末 | Performance | FCP | LCP | TBT | CLS | メモ |
|------|------|-------------|-----|-----|-----|-----|------|
| 2026-06-24 | Mobile | （レポートのみ） | — | — | — | — | [PSI リンク](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)（フェーズ1前） |
| 2026-06-25 | Mobile | **89** | 1.3 s | 1.5 s | 20 ms | 0.019 | [PSI リンク](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/vy4ivjszt5?form_factor=mobile)（フェーズ1後） |
| | | A11y 87 / BP 100 / SEO 100 | | | | | 残課題: レンダーブロック推定 1,040 ms、未使用 CSS 82 KiB、未使用 JS 64 KiB、総転送 3,553 KiB |

**再計測手順**

1. 本番デプロイ後、シークレットウィンドウで `https://trends-dashboard.fly.dev/` を開く
2. [PageSpeed Insights](https://pagespeed.web.dev/) で mobile / desktop を実行
3. 上表に Performance スコアと CWV（lab）を追記

---

## 決定ログ

| 日付 | 決定内容 |
|------|----------|
| 2026-06-26 | PageSpeed 改善タスクを `docs/PERFORMANCE.md` に一本化。フェーズ1（JS defer / フォント / Cache-Control / 不要 CSS）から着手。 |
| 2026-06-26 | フェーズ1 実装: `index.html` / `us_trends.html` の JS defer 化、フォント 400 のみ、`app.py` Cache-Control 修正、`tests/test_cache_headers.py` 追加。 |
| 2026-06-26 | フェーズ1 デプロイ後 PSI モバイル: Performance **89**, LCP 1.5 s, TBT 20 ms, CLS 0.019。残: レンダーブロック推定 1 s、未使用 CSS/JS、総転送 3.5 MB。 |
| 2026-06-26 | フェーズ2 実装: FA サブセット CSS、Bootstrap/FA 自前ホスト、JP `loadCachedDataExternal` タブ遅延 + SSR スキップ。 |

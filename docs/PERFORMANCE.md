# PageSpeed / フロントエンドパフォーマンス改善

**このファイルが PageSpeed Insights（モバイル中心）改善タスクの正本です。**

- ベースライン計測・優先順位・実装チェックリスト・スコア記録はここだけを更新する
- 全体バックログとの関係: [`BACKLOG.md`](BACKLOG.md) の「プロダクト・品質改善」から本ファイルへリンク
- 参照レポート: [PageSpeed Insights（mobile, 2026-06-24）](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)

**最終更新:** 2026-06-28（モバイル LCP 向け Noto 自前ホスト + FA font-display 修正）

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
| **レンダリングブロック JS** | 実装済み（defer） | — |
| **Noto Sans JP** | 自前ホスト済み | デプロイ後モバイル PSI で LCP 確認 |
| **Font Awesome** | サブセット + `font-display:swap` | デプロイ後アイコン表示確認 |
| **静的キャッシュ** | 実装済み | — |
| **初回 API** | JP タブ遅延 + SSR スキップ済み | Network で API 件数確認 |
| **PSI モバイル** | **~60 台**（改善前後ほぼ横ばい） | デプロイ後再計測 |
| **PSI デスクトップ** | **~89**（フェーズ1 効果） | 月次で再記録 |

> **Mobile / Desktop は別 KPI。** 89 はデスクトップ計測。モバイルはもともと 60 前後で、フェーズ1 の JS defer 等は主にデスクトップ・TBT 側に効いている。

---

## ベースライン（2026-06-26 計測）

対象 URL: `https://trends-dashboard.fly.dev/`

| 指標 | 値 | メモ |
|------|-----|------|
| HTML サイズ | 約 252 KB | SSR 行 + 全タブ DOM を含む |
| TTFB | 約 0.56 s | SSR で DB から 5 ソース並列取得 |
| DOM 要素数 | 1,100+ | `div` / `tr` / `section` 合算 |
| `<head>` 同期 JS | 15 本以上 | 自前 JS 合計 約 430 KB |
| 外部 CSS/JS | 約 331 KB | Bootstrap + Font Awesome + Bootstrap JS（cdnjs） |
| 初回 API 呼び出し | 24 本 | `loadCachedDataExternal`（4 並列 × 6 バッチ） |
| 静的 JS Cache-Control | `no-cache` のみ | `application/javascript` 判定漏れ |

### 主なボトルネック（モバイル優先度順）

1. **Noto Sans JP（Google Fonts）** — CSS がレンダーブロック + ページ内容に応じて **40+ woff2** を分割取得
2. `<head>` レンダーブロック CSS — Bootstrap + main.css + fonts CSS
3. Font Awesome webfont — `font-display:block` で描画待ち
4. 全タブ DOM を初回から展開（HTML 肥大・パースコスト）
5. SSR 済みなのに起動時に全カテゴリ API を再取得（フェーズ2 で改善）

---

## 改善ロードマップ

```
フェーズ1  クイックウィン（JS defer / フォント 400 / Cache-Control / 不要 CSS）
    ↓
フェーズ2  転送量・API（FA サブセット / SSR スキップ / 自前ホスト）
    ↓
フェーズ2b モバイル LCP（Noto 自前 / FA font-display swap）  ← いま
    ↓
フェーズ3  DOM 構造（非アクティブタブ遅延レンダリング）
    ↓
フェーズ4  計測・運用（PSI 定期記録 / TTFB / Real User Metrics）
```

各フェーズ完了後、**モバイルとデスクトップを分けて** PSI 再計測し [スコア記録](#スコア記録) に追記する。

---

## フェーズ1 — クイックウィン（小さな差分・効果大）

**目標:** レンダリングブロック JS 解消 + 再訪問キャッシュ修正。**デスクトップ PSI で大幅改善、モバイルは LCP ボトルネックが残る。**

### 1-1 レンダリングブロック JS の解消

- [x] `templates/index.html` — `<head>` 内の自前 JS を `</body>` 直前へ移動
- [x] `templates/us_trends.html` — 同上
- [x] Bootstrap JS を `defer` で読み込み
- [x] 本番デプロイ後 PSI で確認

### 1-2 Web フォントの軽量化

- [x] Noto Sans JP を **400 のみ** に絞る
- [x] US ページ: Inter も **400 のみ** に統一
- [x] `display=swap` を維持（Google Fonts 経由時）

### 1-3 静的ファイル Cache-Control の修正

- [x] `app.py` `set_cache_headers` — `text/javascript` を判定に追加
- [x] テスト: `tests/test_cache_headers.py`

### 1-4 不要 CSS の除去（index / us）

- [x] `index.html` から `data-status.css` / `subscription.css` を外す

### フェーズ1 完了ゲート

- [x] **デスクトップ** PSI: Performance **89**, LCP 1.5 s, TBT 20 ms, CLS 0.019
- [x] **モバイル** PSI: **~60 台**（LCP 改善は限定的 — CSS/フォントが主因）
- [x] 静的 JS の Cache-Control が意図どおり
- [ ] モバイル LCP — フェーズ2b へ

---

## フェーズ2 — 転送量・API 削減

**目標:** 初回転送削減 + 起動時 API 呼び出し削減。

### 2-1 Font Awesome のサブセット化

- [x] `scripts/build_fontawesome_subset.py` → `static/css/fontawesome-subset.css`
- [x] cdnjs 依存を外す（`partials/vendor_assets.html`）

### 2-2 SSR 済みソースの API スキップ

- [x] JP: `loadCachedDataExternal` タブ単位 + SSR スキップ
- [x] `tbodyHasTrendDataRows` を `app-common.js` に追加

### 2-3 サードパーティ CDN の見直し

- [x] Bootstrap / FA webfonts を自前ホスト

### 2-4 モバイル LCP — Noto 自前ホスト（フェーズ2b）

- [x] `scripts/build_noto_sans_jp.py` — Fontsource japanese-400 woff2（約 1.1 MB）
- [x] `static/css/noto-sans-jp.css` + `templates/partials/jp_web_font.html`
- [x] `index.html` から Google Fonts（Noto）を除去
- [ ] デプロイ後モバイル PSI 再計測

### 2-5 モバイル LCP — FA font-display

- [x] `font-display:swap` に変更（build スクリプト）
- [x] 不要 `@font-face`（FA5 / v4 / 重複）を除外
- [ ] デプロイ後 iPhone / Android でアイコン確認

### フェーズ2 完了ゲート

- [ ] 初回 API 呼び出し数を Network で確認
- [ ] **モバイル** PSI 再計測（目標: 60 台 → 70 台）
- [ ] **デスクトップ** PSI が 89 付近を維持

---

## フェーズ3 — DOM・構造（中〜大規模）

**目標:** HTML サイズ・DOM ノード数を削減。LCP / TBT のさらなる改善。

### 3-1 非アクティブタブの遅延レンダリング

- [ ] 初回は「全部入り」タブのみフル DOM、他タブは初回表示時にマウント
- [ ] SEO: 全部入りタブの SSR は維持

### 3-2 HTML / CSS の整理

- [ ] `main.css`（約 136 KB）の未使用ルール監査

### フェーズ3 完了ゲート

- [ ] HTML サイズ **200 KB 未満**
- [ ] DOM ノード数 **800 未満**
- [ ] モバイル PSI 再計測

---

## フェーズ4 — 計測・運用

- [ ] PSI モバイル / デスクトップを月 1 回記録（**端末列を必ず分ける**）
- [ ] Search Console Core Web Vitals と突合
- [ ] TTFB 監視（SSR DB 読み取り・コールドスタート時）

---

## スコア記録

| 日付 | 端末 | Performance | FCP | LCP | TBT | CLS | メモ |
|------|------|-------------|-----|-----|-----|-----|------|
| 2026-06-24 | Mobile | **~60** | — | — | — | — | [PSI](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)（フェーズ1前・ベースライン） |
| 2026-06-25 | Desktop | **89** | 1.3 s | 1.5 s | 20 ms | 0.019 | [PSI](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/vy4ivjszt5?form_factor=desktop)（フェーズ1後）※旧記録を Desktop に訂正 |
| 2026-06-27 | Mobile | **63** | — | — | — | — | フェーズ2 + iPhone ホットフィックス後。A11y 87 / BP 100 / SEO 100 |
| 2026-06-28 | Mobile | （未計測） | — | — | — | — | フェーズ2b: Noto 自前 + FA swap 後に再計測 |

**再計測手順**

1. 本番デプロイ後、シークレットウィンドウで URL を開く
2. [PageSpeed Insights](https://pagespeed.web.dev/) で **携帯電話** / **デスクトップ** を**別々に**実行
3. 上表に端末・Performance・CWV を追記

---

## 決定ログ

| 日付 | 決定内容 |
|------|----------|
| 2026-06-26 | PageSpeed 改善を `docs/PERFORMANCE.md` に一本化。フェーズ1 着手。 |
| 2026-06-26 | フェーズ1 実装: JS defer、フォント 400 のみ、Cache-Control 修正。 |
| 2026-06-26 | フェーズ1 後 PSI: **Desktop 89** / **Mobile ~60**。89 を Mobile と誤記していたため訂正。 |
| 2026-06-26 | フェーズ2: FA サブセット、Bootstrap/FA 自前ホスト、JP API 遅延 + SSR スキップ。 |
| 2026-06-27 | フェーズ2 後 PSI Mobile **63**（60 台から横ばい〜微増）。iPhone ホットフィックス（FA subset / SSR resync）。 |
| 2026-06-28 | フェーズ2b: Noto Sans JP 自前ホスト（Google Fonts レンダーブロック除去）、FA `font-display:swap` + `@font-face` 整理。 |

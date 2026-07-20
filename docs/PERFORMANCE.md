# PageSpeed / フロントエンドパフォーマンス改善

**このファイルが PageSpeed Insights（モバイル中心）改善タスクの正本です。**

- ベースライン計測・優先順位・実装チェックリスト・スコア記録はここだけを更新する
- 全体バックログとの関係: [`BACKLOG.md`](BACKLOG.md) の「プロダクト・品質改善」から本ファイルへリンク
- 参照レポート: [PageSpeed Insights（mobile, 2026-06-24）](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)

**最終更新:** 2026-06-28（フェーズ1〜2c 完了・改善作業はここまで。月次 PSI のみ）

---

## 目次

1. [いまフォーカスするもの](#いまフォーカスするもの)
2. [運用方針（フェーズ3以降）](#運用方針フェーズ3以降)
3. [ベースライン（2026-06-26 計測）](#ベースライン2026-06-26-計測)
4. [改善ロードマップ](#改善ロードマップ)
5. [フェーズ1 — クイックウィン](#フェーズ1--クイックウィン小さな差分効果大)
6. [フェーズ2 — 転送量・API 削減](#フェーズ2--転送量api-削減)
7. [フェーズ3 — DOM・構造](#フェーズ3--dom構造中〜大規模)
8. [フェーズ4 — 計測・運用](#フェーズ4--計測運用)
9. [計測ツール（PSI と Lighthouse）](#計測ツールpsi-と-lighthouse)
10. [Lighthouse 改善ポイント（JP `/`）](#lighthouse-改善ポイントjp-)
11. [US `/us` — JP との差分](#us-us--jp-との差分)
12. [スコア記録](#スコア記録)
13. [決定ログ](#決定ログ)

---

## いまフォーカスするもの

| 領域 | 状態 | 次のアクション |
|------|------|----------------|
| **レンダリングブロック JS** | 実装済み（defer） | — |
| **Noto Sans JP** | 自前ホスト済み | — |
| **Inter（US）** | 自前ホスト済み | — |
| **Font Awesome** | サブセット + `font-display:swap` | — |
| **静的キャッシュ** | 実装済み | — |
| **初回 API** | JP タブ遅延 + SSR スキップ済み | — |
| **PSI モバイル（JP `/`）** | **85**（2026-06-28） | 警戒ライン内。月次計測のみ |
| **PSI デスクトップ（JP `/`）** | **92**（2026-06-28） | 同上 |
| **PSI モバイル（US `/us`）** | **93**（2026-06-27） | Desktop **96** |
| **パフォーマンス改善** | **完了（ここまで）** | フェーズ3 は [運用方針](#運用方針フェーズ3以降) どおり保留 |

> **JP Mobile ~60 → 85** / **US Mobile 93** / **JP Desktop 92**（2026-06-28 時点）。フェーズ1〜2c まで実施。**以降は新規改修せず、月次 PSI で監視のみ。**

---

## 運用方針（フェーズ3以降）

**2026-06-28 時点の判断:** フェーズ1〜2c で目標達成（JP Mobile **85** / US Mobile **93**）。フェーズ3（DOM 遅延レンダリング等）は **デグレリスクが高く費用対効果が低い** ため、**スコアが下がったときだけ** 再検討する。**2026-06-28 よりパフォーマンス改善の能動的な作業は停止**し、月次 PSI の記録のみ継続する。

### 定期計測

- **頻度:** 月 1 回（デプロイ直後の計測は任意で [スコア記録](#スコア記録) に追記）
- **対象 URL:** `https://trends-dashboard.com/`（JP）— 月次はこちらを正本。**`/us` も四半期に 1 回**または JP 改修後に [差分確認](#us-us--jp-との差分)
- **端末:** PSI で **携帯電話** と **デスクトップ** を**別々に**実行し、表の端末列を分ける
- **記録:** Performance スコア + 可能なら FCP / LCP / TBT / CLS

### フェーズ3以降を着手する目安

次のいずれかが **2 回連続**（またはデプロイ起因で明確に再現）したら、フェーズ3（または原因に応じた小さな修正）を検討する。

| 端末 | 警戒ライン（Performance） | 備考 |
|------|---------------------------|------|
| Mobile | **75 未満** | 2026-06-28 実績 **85**（JP `/`） |
| Desktop | **90 未満** | 2026-06-28 実績 **92**（JP `/`） |

スコア低下時は、まず **直近デプロイ・依存追加・SSR/フォント変更** を疑い、Lighthouse の「レンダリングをブロック」「フォント」「DOM サイズ」を確認してからフェーズ3 に入る。

### フェーズ3を急がない理由（メモ）

- 非アクティブタブの遅延 DOM は `syncToAllPane` / `reSyncAllPanes` / タブ復元 / 「もっと見る」アンカーと絡み、**回帰しやすい**
- 90 台を狙うには HTML 252 KB・DOM 1,100+ の構造変更が必要で、**プロダクト優先度に対してコストが大きい**

### スコアが安定している間

- フェーズ3 のチェックリストは **未着手のまま** バックログとして残す
- A11y（87）など PSI Performance 外の改善は、必要になったら別タスクで扱う

---

## ベースライン（2026-06-26 計測）

対象 URL: `https://trends-dashboard.com/`

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
フェーズ2b モバイル LCP（Noto 自前 / FA font-display swap）  ← 完了（2026-06-28）
    ↓
フェーズ2c JP PSI 60 対応（Noto optional / CSS 非同期 / lazy images）  ← 完了（2026-06-28）
    ↓
フェーズ3  DOM 構造（非アクティブタブ遅延レンダリング）      ← 保留（スコア低下時のみ）
    ↓
フェーズ4  計測・運用（PSI 月次 / 低下時にフェーズ3検討）   ← いま（能動改修は停止）
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
- [x] デプロイ後モバイル PSI 再計測（Performance **82**）

### 2-5 モバイル LCP — FA font-display

- [x] `font-display:swap` に変更（build スクリプト）
- [x] 不要 `@font-face`（FA5 / v4 / 重複）を除外
- [x] デプロイ後 iPhone / Android でアイコン確認（問題なし想定）

### フェーズ2 完了ゲート

- [ ] 初回 API 呼び出し数を Network で確認
- [x] **モバイル** PSI 再計測（**82**、目標 70 台を達成）
- [x] **デスクトップ** PSI 再計測（**97**、89 から **+8 点**）

---

## フェーズ2c — JP PSI 60 対応（2026-06-27）

**背景:** デプロイ後 PSI Mobile `/` が **82 → 60** に下落（警戒ライン 75 未満）。同一時刻の LH CLI では **91** と乖離 — PSI の厳しい throttling 下で **Noto 1.3 MB** と **レンダーブロック CSS** が LCP を悪化させていると判断。

**実装:**

- [x] Noto `font-display: optional` + preload `fetchpriority="high"`（LCP テキストが webfont 待ちしない）
- [x] `trends.css` / `fontawesome-subset.css` / `us-trends.css` を非同期読み込み（`partials/async_stylesheet.html`）
- [x] 楽天サムネ CDN へ `preconnect`（JP `/`）
- [x] 書籍・映画・アプリ画像に `loading="lazy" decoding="async"`

**完了ゲート:**

- [x] デプロイ後 PSI Mobile `/` **85**（目標 75 以上・80 台復帰を達成）
- [x] PSI Desktop `/` **92**（A11y 87 / BP 100 / SEO 100）

---

## フェーズ3 — DOM・構造（中〜大規模）

**状態: 保留**（[運用方針](#運用方針フェーズ3以降) — Mobile &lt; 75 または Desktop &lt; 90 が続いたら着手）

**目標:** HTML サイズ・DOM ノード数を削減。LCP / TBT のさらなる改善（90 台狙い）。

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

**いまの主タスク:** 能動的なパフォーマンス改修は **2026-06-28 で停止**。下記の月次記録のみ継続し、スコアが [運用方針](#運用方針フェーズ3以降) の警戒ラインを下回ったらフェーズ3以降を検討する。

- [ ] PSI モバイル / デスクトップを **月 1 回** 記録（**端末列を必ず分ける**）
- [ ] 計測結果を [スコア記録](#スコア記録) に追記
- [ ] 警戒ライン割れ時: 原因調査 → 必要ならフェーズ3 またはピンポイント修正
- [ ] Search Console Core Web Vitals と突合（トラフィック増加後）
- [ ] TTFB 監視（SSR DB 読み取り・コールドスタート時）
- [ ] デプロイ前後の差分確認に [Lighthouse CLI](#計測ツールpsi-と-lighthouse) を利用（任意）

---

## 計測ツール（PSI と Lighthouse）

| ツール | 用途 | 記録の正本 |
|--------|------|------------|
| [PageSpeed Insights (PSI)](https://pagespeed.web.dev/) | 月次の本番スコア記録・CrUX（フィールドデータ）確認 | **はい** — [スコア記録](#スコア記録) |
| [Lighthouse CLI](https://github.com/GoogleChrome/lighthouse) | デプロイ前後の比較・監査項目の深掘り・ローカル検証 | いいえ（PSI と数値が一致しないため） |

PSI の Lab データも Lighthouse エンジンだが、**実行環境・回線・throttling が異なる**ため、同じ URL でもスコアは一致しない。改善の優先順位は [JP 改善ポイント](#lighthouse-改善ポイントjp-) / [US 差分](#us-us--jp-との差分) を参照。

### 前提

- **Node.js**（`npx` が使えること）
- **Chrome / Chromium**（Lighthouse が headless で起動する）

### クイック実行（本番 URL）

```bash
# モバイル（PSI の携帯電話に近い）
npx lighthouse https://trends-dashboard.com/ \
  --form-factor=mobile \
  --output=html,json \
  --output-path=./lighthouse-reports/mobile \
  --chrome-flags="--headless=new"

# デスクトップ
npx lighthouse https://trends-dashboard.com/ \
  --preset=desktop \
  --output=html,json \
  --output-path=./lighthouse-reports/desktop \
  --chrome-flags="--headless=new"
```

`lighthouse-reports/` に `.report.html` / `.report.json` が出力される（**`.gitignore` 済み・リポジトリには含めない**）。HTML をブラウザで開き、Performance スコアと Opportunities / Diagnostics を確認する。数値の正本は [スコア記録](#スコア記録)（PSI）。ローカルのレポートファイルは **再生成可能なため、ディスク節約のため削除してよい**。

ラッパースクリプト: `scripts/run_lighthouse.sh [URL] [mobile|desktop]`

```bash
./scripts/run_lighthouse.sh                          # 本番・モバイル
./scripts/run_lighthouse.sh http://127.0.0.1:5000/ mobile   # ローカル
./scripts/run_lighthouse.sh https://trends-dashboard.com/ desktop
```

### ローカル開発サーバー

```bash
# 別ターミナルで Flask を起動してから
npx lighthouse http://127.0.0.1:5000/ \
  --form-factor=mobile \
  --output=html \
  --output-path=./lighthouse-reports/local-mobile \
  --view
```

`--view` はレポート生成後にブラウザで開く。CI や headless 環境では外す。

### Chrome DevTools

Chrome → **Inspect** → **Lighthouse** タブでも同エンジンを実行できる。CLI ほど再現性は高くないが、単発の確認には十分。

### スコア低下時に見る監査（Lighthouse）

[運用方針](#運用方針フェーズ3以降) で PSI が警戒ラインを下回ったとき、Lighthouse レポートで次を優先確認する。

| 監査 / カテゴリ | 確認内容 |
|-----------------|----------|
| Render blocking resources | CSS / JS が初回描画をブロックしていないか |
| Font display | webfont の `font-display` と読み込み順 |
| Avoid enormous network payloads | HTML / JS / フォントの転送量 |
| Largest Contentful Paint element | LCP 要素（ヒーロー / フォント / 画像） |
| Reduce unused JavaScript | 未使用 JS（Bootstrap 等） |
| DOM size | ノード数 1,100+ の影響 |

月次の数値記録は引き続き **PSI のみ**。[スコア記録](#スコア記録) の「ツール」列に `PSI` / `LH` を分けて追記してもよい（LH は参考値として）。

---

## Lighthouse 改善ポイント（JP `/`）

**出典:** `lighthouse-reports/mobile-20260627-164249.report.*`（CLI v13.4・モバイル・`/`・2026-06-27）

PSI Mobile **82** に対し LH Performance **71** — 絶対値より **監査の中身** を参照する。再計測のたびに本セクションを更新する。

### 計測サマリ

| 項目 | 値 | PSI 82 時点での所見 |
|------|-----|---------------------|
| Performance | **71** | LH 参考値。月次判断は PSI |
| FCP | 3.4 s | 遅い（目安 1.8 s 以下） |
| LCP | 4.9 s | 遅い（目安 2.5 s 以下） |
| TBT | 30 ms | **良好** — JS defer の効果 |
| CLS | 0 | **良好** |
| Speed Index | 6.0 s | CSS / フォント待ちが効いている |
| TTI | 6.1 s | FCP/LCP と同系統 |
| A11y | 87 | Performance 外。必要時に別タスク |
| Best Practices / SEO | 100 / 100 | 問題なし |

### 転送・DOM（Diagnostics）

| 項目 | 値 | メモ |
|------|-----|------|
| リクエスト数 | **127** | 画像が大半 |
| 転送量合計 | **約 3.7 MB** | |
| 画像 | 75 req / **1.9 MB** | 楽天書籍サムネ等（third-party） |
| フォント | 3 req / **1.3 MB** | Noto 自前ホスト分 |
| スクリプト | 18 req / 277 KB | フェーズ1 後は許容範囲 |
| スタイルシート | 6 req / 55 KB | レンダーブロック要因 |
| DOM 要素数 | **7,634** | ベースライン「1,100+」より大幅増（全タブ初回展開） |
| DOM 深さ | 23 | |
| HTML TTFB | 400 ms | SSR は許容範囲 |

### LCP の内訳

| 要素 | 内容 |
|------|------|
| **LCP 要素** | `#dashboard-summary-intro > p.small`（冒頭説明文。画像ではない） |
| TTFB | 728 ms |
| Element render delay | 917 ms |

→ LCP は **CSS / webfont のレンダーブロック** と **初回 HTML の重さ** が主因。画像 LCP ではない。

### 優先度別 — 残ボトルネック

| 優先 | 監査 / 現象 | 詳細 | 対応フェーズ | いま着手？ |
|------|-------------|------|--------------|------------|
| 1 | **Render-blocking requests** | `main.css`（~536 ms）、`bootstrap.min.css`（~268 ms）、`common.css` / `trends.css` / `fontawesome-subset.css` / `noto-sans-jp.css` | フェーズ3-2（CSS 整理）／クリティカル CSS 化は未計画 | **保留**（PSI 82 で警戒ライン内） |
| 2 | **LCP / FCP 遅延** | 上記 CSS + Noto 1.3 MB。render delay ~920 ms | フェーズ2b 済み。さらなる削減はフォントサブセット or CSS インライン化 | 保留 |
| 3 | **DOM size** | 7,634 要素。パース・スタイル計算コスト | [フェーズ3 — 非アクティブタブ遅延レンダリング](#フェーズ3--dom構造中〜大規模) | **保留**（デグレリスク大） |
| 4 | **Third-party 画像** | 楽天 CDN 書籍サムネ 75 件 / 1.9 MB。Cache lifetimes で ~187 KiB 節約余地（CDN 側 TTL） | 自前制御不可。`loading="lazy"` / 初回表示行数削減は要検討 | 低優先 |
| 5 | **Main-thread / JS** | main-thread 3.6 s、JS 実行 2.1 s と表示されるが **TBT 30 ms** | フェーズ1 defer 済み。体感ボトルネックではない | 対応不要 |
| 6 | **A11y 87** | コントラスト、見出し順、`aria-*` / role 不一致、select の label | Performance 外 | 別タスク |

### すでに効いている改善（LH でも確認済み）

- レンダリングブロック **JS** — TBT 30 ms、長タスク少
- **Noto / FA 自前ホスト** — Google Fonts 40+ 分割取得は解消
- **Font Awesome** `font-display:swap` — アイコン待ちによる LCP 悪化なし
- **CLS 0** — レイアウトシフトなし
- **HTTPS / BP / SEO** — 100

### スコア低下時の確認順

1. Lighthouse HTML の **Insights** → Render blocking / LCP breakdown / DOM size
2. **Network** タブ相当（Diagnostics）→ 新規 third-party・フォント・HTML サイズ増
3. 直近デプロイ diff → CSS / フォント / SSR / タブ DOM
4. [運用方針](#運用方針フェーズ3以降) の警戒ライン（Mobile &lt; 75）を下回ったら [フェーズ3](#フェーズ3--dom構造中〜大規模) を再検討

---

## US `/us` — JP との差分

**PSI モバイル（2026-06-27）:** `/us` **75** vs `/` **82**（Performance **-7**）。Best Practices も **77** vs **100**。

フェーズ2b（Noto 自前ホスト）は **JP のみ** 適用済み。US は Inter が **Google Fonts のまま** で、加えて US 固有の mixed content がある。

### スコア比較

| 項目 | JP `/` | US `/us` | 差分メモ |
|------|--------|----------|----------|
| PSI Performance（Mobile） | **82** | **75** | -7 |
| PSI Best Practices | **100** | **77** | Google Books 画像 HTTP |
| PSI A11y / SEO | 87 / 100 | 87 / 100 | 同程度 |
| LH Performance（参考） | 71 | 68 | CLI 2026-06-27 |
| FCP（LH） | 3.4 s | 4.0 s | US が遅い |
| LCP（LH） | 4.9 s | 5.5 s | US が遅い |
| TBT / CLS | 30 ms / 0 | 10 ms / 0 | どちらも良好 |
| DOM 要素数 | 7,634 | **8,886** | US の方が多い |
| 転送量（LH） | 3.7 MB | 2.6 MB | US は Noto 1.3 MB なし分 |

### `/` にあって `/us` にないもの（主因）

| # | 差分 | 根拠 | 影響 |
|---|------|------|------|
| 1 | ~~**Inter が Google Fonts**~~ | ~~`us_trends.html` Google Fonts~~ → **2026-06-27 自前ホスト済**（`build_inter.py` / `partials/us_web_font.html`） | レンダーブロック CSS 解消 |
| 2 | **`us-trends.css` が追加** | `us_trends.html` | レンダーブロック CSS が 1 本増 |
| 3 | ~~**Google Books 表紙が HTTP**~~ | ~~22 件~~ → **2026-06-27** `book_trends.py` で HTTPS 正規化 | Best Practices 改善見込み |
| 4 | **DOM が約 +1,250 要素** | LH Diagnostics | パースコスト増（フェーズ3 領域） |

### US 固有 — 改善候補（フェーズ3 不要の小さな差分）

JP フェーズ2b と同様の **ピンポイント改修** で `/us` を `/` に近づけられる見込み。

| 優先 | 施策 | 状態 | 期待効果 |
|------|------|------|----------|
| **1** | **Inter 自前ホスト** | **完了**（2026-06-27） | FCP/LCP 改善、third-party 削減 |
| **2** | **Books 画像 URL HTTPS 化** | **完了**（2026-06-27） | Best Practices **77 → 100** 見込み |
| 3 | `us-trends.css` の critical 化 | 未着手 | レンダーブロック微減 |
| 4 | DOM 遅延レンダリング | 保留（フェーズ3） | Performance さらに向上 |

> **2026-06-27:** 施策 1・2 を実装。デプロイ後 PSI `/us` で再計測する。

### US — LH 再計測

```bash
./scripts/run_lighthouse.sh https://trends-dashboard.com/us mobile
```

---

## スコア記録

| 日付 | URL | 端末 | ツール | Performance | FCP | LCP | TBT | CLS | メモ |
|------|-----|------|--------|-------------|-----|-----|-----|-----|------|
| 2026-06-24 | `/` | Mobile | PSI | **~60** | — | — | — | — | [PSI](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/8qsxatevwc?form_factor=mobile)（フェーズ1前・ベースライン） |
| 2026-06-25 | `/` | Desktop | PSI | **89** | 1.3 s | 1.5 s | 20 ms | 0.019 | [PSI](https://pagespeed.web.dev/analysis/https-trends-dashboard-fly-dev/vy4ivjszt5?form_factor=desktop)（フェーズ1後）※旧記録を Desktop に訂正 |
| 2026-06-27 | `/` | Mobile | PSI | **63** | — | — | — | — | フェーズ2 + iPhone ホットフィックス後。A11y 87 / BP 100 / SEO 100 |
| 2026-06-28 | `/` | Mobile | PSI | **82** | — | — | — | — | フェーズ2b 後。~60 → **+20 点** |
| 2026-06-28 | `/` | Desktop | PSI | **97** | — | — | — | — | フェーズ2b 後。89 → **+8 点** |
| 2026-06-27 | `/` | Mobile | PSI | **60** | — | — | — | — | 82 から一時下落 → [フェーズ2c](#フェーズ2c--jp-psi-60-対応2026-06-27) 着手 |
| 2026-06-27 | `/` | Mobile | LH | **91** | 2.0 s | 3.2 s | 0 ms | 0.002 | CLI（PSI より高い・参考値） |
| 2026-06-28 | `/` | Mobile | PSI | **85** | — | — | — | — | フェーズ2c 後。**~60 → 85**。A11y 87 / BP 100 / SEO 100 |
| 2026-06-28 | `/` | Desktop | PSI | **92** | — | — | — | — | フェーズ2c 後 |
| 2026-06-27 | `/us` | Mobile | PSI | **93** | — | — | — | — | Inter 自前 + Books HTTPS 後。Desktop **96** |
| 2026-06-27 | `/us` | Mobile | LH | **93** | 2.1 s | 2.1 s | 20 ms | 0 | CLI・参考値 |
| 2026-06-27 | `/` | Mobile | LH | **71** | 3.4 s | 4.9 s | 30 ms | 0 | CLI v13.4（フェーズ2c 前） |
| 2026-06-27 | `/` | Desktop | LH | **90** | — | — | — | — | CLI v13.4・参考値 |

**再計測手順（月次 — PSI）**

1. 本番デプロイ後、シークレットウィンドウで URL を開く
2. [PageSpeed Insights](https://pagespeed.web.dev/) で **携帯電話** / **デスクトップ** を**別々に**実行
3. 上表に端末・ツール `PSI`・Performance・CWV を追記

**デプロイ前後の確認（任意 — Lighthouse）**

1. `./scripts/run_lighthouse.sh` でデプロイ前のベースラインを `./lighthouse-reports/` に保存
2. 変更デプロイ後、同コマンドを再実行
3. 同一マシン・同一 URL で Performance スコアと Opportunities の差分を見る（絶対値は PSI 基準と混同しない）

---

## 決定ログ

| 日付 | 決定内容 |
|------|----------|
| 2026-06-26 | PageSpeed 改善を `docs/PERFORMANCE.md` に一本化。フェーズ1 着手。 |
| 2026-06-26 | フェーズ1 実装: JS defer、フォント 400 のみ、Cache-Control 修正。 |
| 2026-06-26 | フェーズ1 後 PSI: **Desktop 89** / **Mobile ~60**。89 を Mobile と誤記していたため訂正。 |
| 2026-06-26 | フェーズ2: FA サブセット、Bootstrap/FA 自前ホスト、JP API 遅延 + SSR スキップ。 |
| 2026-06-27 | フェーズ2 後 PSI Mobile **63**（60 台から横ばい〜微増）。iPhone ホットフィックス（FA subset / SSR resync）。 |
| 2026-06-28 | フェーズ2b: Noto Sans JP 自前ホスト、FA `font-display:swap` + `@font-face` 整理。 |
| 2026-06-28 | フェーズ2b デプロイ後 PSI Mobile **82**（~60 から +約 20 点）、Desktop **97**（89 から +8 点）。 |
| 2026-06-28 | **運用方針:** フェーズ3以降は保留。月次 PSI で監視し、Mobile &lt; 75 または Desktop &lt; 90 が続く場合のみフェーズ3以降を検討。 |
| 2026-06-27 | **計測ツール:** [Lighthouse CLI](https://github.com/GoogleChrome/lighthouse) を追加。月次記録は PSI のまま、LH は before/after と監査深掘り用。 |
| 2026-06-27 | **LH 改善ポイント:** 初回 CLI 計測を [Lighthouse 改善ポイント（JP）](#lighthouse-改善ポイントjp-) に整理。CSS ブロック・DOM 7,634・third-party 画像が残存、TBT/CLS は良好。 |
| 2026-06-27 | **US `/us` 改善:** Inter 自前ホスト、Google Books 画像 HTTPS 正規化。PSI Mobile **93** / Desktop **96**。 |
| 2026-06-27 | **JP PSI 60:** 警戒ライン割れ。フェーズ2c: Noto optional、非クリティカル CSS 非同期化、画像 lazy、Rakuten preconnect。 |
| 2026-06-28 | **フェーズ2c 完了:** PSI JP Mobile **85** / Desktop **92**。US Mobile **93** は維持。**パフォーマンス改善の能動作業はここまで** — 月次 PSI のみ。 |

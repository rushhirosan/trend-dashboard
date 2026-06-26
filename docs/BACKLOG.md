# Backlog — 今後の To Do 集約

**このファイルが将来の改善・拡張・商品化タスクの正本です。**  
方針変更・ステップ完了・新規課題はここだけを更新する（ルート `todo.md` / 旧 `monetization.md` は使わない）。

**更新ルール**

- 完了 → 該当 `[ ]` を `[x]` に
- 方針変更 → [決定ログ](#決定ログ) に1行
- 週次の数値 → [週次メモ](#週次メモ)
- 日次サマリー品質・SLA の詳細手順 → [`summary_pattern_a_phase1.md`](summary_pattern_a_phase1.md)

**最終更新:** 2026-06-26

---

## 目次

1. [いまフォーカスするもの](#いまフォーカスするもの)
2. [AIサマリー・マネタイズ](#aiサマリー・マネタイズ)
3. [プラットフォーム・運用](#プラットフォーム・運用)
4. [ソース・API 拡張](#ソースapi-拡張)
5. [プロダクト・品質改善](#プロダクト品質改善)
6. [決定ログ・KPI](#決定ログkpi)

---

## いまフォーカスするもの

| 領域 | 状態 | 次のアクション |
|------|------|----------------|
| **AIサマリー** | フェーズ2a（Waitlist 稼働） | 本番 Waitlist E2E + 2〜4週の関心検証 |
| **定時取得** | 1536MB で JP/US 54/54 安定 | Grafana OOM アラートの手動設定（未なら） |
| **データ保持** | DB / 原稿 10日・週次30日 purge 実装済 | 03:00 JST 自動 + git 原稿は `--summaries-only` で必要時 |

---

## AIサマリー・マネタイズ

トレンドダッシュボードの **AI日次／週次サマリー** を商品化する計画。

### プロダクトの位置づけ

| レイヤー | 役割 | 課金 |
|---------|------|------|
| **ダッシュボード** | 複数ソースの生トレンド（JP/US） | **無料**（集客・信頼の入口） |
| **AIサマリー** | 順位の動き・カテゴリ横断・一行結論 | **有料候補** |
| **X 20時投稿** | 急上昇3件のティーザー | 無料（導線） |

- 原稿: [`docs/summaries/`](summaries/README.md)（サイト未公開）
- 品質・配信 SLA: [`summary_pattern_a_phase1.md`](summary_pattern_a_phase1.md)
- Fake door: `templates/partials/ai_summary_fake_door.html`
- Waitlist: `POST /api/waitlist/ai-summary`
- **本命案:** A（フリーミアム + メール）。並行検証可: B（note / Substack）

### ロードマップ

```
フェーズ1  原稿生成・レビュー・パターンA（課金なし）
    ↓
フェーズ2a  トップ一行結論 + Waitlist ← いまここ
    ↓
フェーズ2b  限定有料（10〜30人）
    ↓
フェーズ3   サイト内サマリー + 配信自動化
```

**フェーズ1 → 2 ゲート:** 4週欠配ゼロ / 遅延許容 / リンク許容 / 品質平均 ≥ 3.5（詳細は pattern A doc）

### 進捗チェックリスト

#### フェーズ1 — 原稿・品質（課金前）

**1-1 日次**

- [x] GHA `ai-daily-summary.yml` 稼働
- [x] `docs/summaries/daily/` 蓄積
- [ ] 直近7日で意図しない欠配なし
- [ ] 失敗時再生成手順を1回以上実施

**1-2 週次**

- [x] GHA `ai-weekly-summary.yml`
- [x] `docs/summaries/weekly/` に週次あり
- [ ] 直近2週が「日次羅列」でない（人レビュー）

**1-3 レビューゲート**

- [ ] draft → approved 運用合意
- [ ] サンプル1本以上 `status: approved`
- [ ] 毎日チェックリストを回した記録

**1-4 SLA・品質記録**

- [ ] 記録シート開始
- [ ] 4週分の品質・欠配記録 → 出口判定

**1-5 X との役割分担**

- [x] 夜=X 急上昇 / 朝=AIサマリー
- [ ] X 文案とダッシュ CTA の文言統一

#### フェーズ2a — Waitlist（課金なし）

- [x] 一行結論抽出・Fake door 実データ・Waitlist API/DB/UI
- [x] GA4 `fake_door_view` / `waitlist_*`
- [ ] **本番 Waitlist 登録 E2E**
- [ ] 2〜4週: view / click / 登録数記録（目安 JP 50件）

#### フェーズ2b — 限定有料（案 A）

- [ ] SKU・価格確定
- [ ] 配信ルート決定（Subscription / Stripe 手動 / 他）
- [ ] 初回課金者1人に SLA 内配信
- [ ] 有料会員10人 + 2週継続率

#### フェーズ3 — サイト内 + 自動化

- [ ] `/summary/` 系ルート（approved のみ）
- [ ] 10:30 JST 自動配信 + 失敗アラート
- [ ] 週次バンドル同梱

#### 並行検証（任意）

| 案 | 主な未完了 |
|----|-----------|
| **B** note/Substack | 媒体決定 → 5本投稿 → CTA + UTM |
| **C** B2B | 1枚提案 → サンプル配信 → 契約1件 |
| **D** 寄付 | BMC 本番 username / 特典ルール |
| **E** タイムボックス | 10:30 / 月11:00 を商品文に明記 |

### マネタイズ案（参照）

| ID | 案 | 単価イメージ |
|----|-----|-------------|
| A | フリーミアム + メール | 月 ¥500〜980 / Bundle ¥1,500〜2,000 |
| B | note / Substack | 月 ¥500〜 |
| C | B2B ブリーフィング | 月 ¥9,800〜 |
| D | Buy Me a Coffee | 任意 |
| E | タイムボックス約束 | A/B の SLA を SKU 化 |

詳細ステップ（Phase 2b 以降の手順書）は必要になったら [決定ログ](#決定ログ) から Issue 化するか、pattern A doc に追記。

### トラブル時

| 状況 | アクション |
|------|-----------|
| 品質が低い | レビュー強化 / `generate_ai_daily_summary.py` プロンプト |
| approved が間に合わない | 遅延可、draft は出さない / 短縮テンプレ |
| Waitlist が伸びない | X・note 導線 / 一行結論 A/B |
| リンク大量死 | リンクチェック脚本検討 |

### 関連コード

| 種別 | パス |
|------|------|
| 日次 / 週次生成 | `scripts/generate_ai_daily_summary.py`, `generate_ai_weekly_summary.py` |
| Fake door | `templates/partials/ai_summary_fake_door.html`, `static/js/ai-summary-fake-door.js` |
| Waitlist | `routes/waitlist_routes.py`, `services/waitlist/` |
| サブスク（休眠） | `services/subscription/`, `ENABLE_SUBSCRIPTION_UI` |

---

## プラットフォーム・運用

### 定時取得・OOM（2026-06 対応済み / 残タスク）

**完了**

- [x] JP/US subprocess フェーズ分割（`TRENDS_SCHEDULER_SUBPROCESS_PHASES`）
- [x] JP 失敗時 US スキップ / 部分失敗で slot 完了マークしない
- [x] 地域別 `cache_status` キー
- [x] Fly **1536MB** + cgroup memory_watchdog
- [x] `captured_at` スロット窓チェック + Discord 警告
- [x] `trend_daily_snapshots` / `scheduler_slot_run` **10日 purge**（03:00 JST）
- [x] `docs/summaries` 日次10日・週次30日 purge（同一スクリプト）
- [x] `scripts/inspect_scheduler_slots.py --business-day`
- [x] `docs/grafana-oom-alerts.md`

**残タスク**

- [ ] **Grafana** で OOM / `Worker SIGKILL` アラートを UI 設定（doc 参照）
- [ ] 6/20 の 07/13 スナップショット（`captured_at` ~16:02）を要再取得か判断 — 必要なら成功スロット後に re-backfill
- [ ] 1536MB でも OOM 再発時: JP 2分割 / KKJ scheduler 除外 / 1792MB 検討（`fetch_all_categories=False` は不可）

**運用メモ（調査記録）**

- backfill 行は `captured_at_ok: false` になりうる（期待どおり）
- 確認: `scripts/purge_snapshot_retention.py`, `scripts/backfill_missing_snapshot_slots.py`

---

## ソース・API 拡張

### Reddit

- [ ] Reddit API 申請結果待ち（2025-11-22 申請）— [`REDDIT_API_APPLICATION_IMPROVED.md`](REDDIT_API_APPLICATION_IMPROVED.md)

### Reddit 却下時の代替

- [ ] Dev.to API 調査・実装
- [ ] その他: Product Hunt API / GitHub Trending / Mastodon

---

## プロダクト・品質改善

### 優先度: 高

**エラー・監視**

- [x] Discord Webhook 通知
- [ ] 構造化ログ（JSON）
- [ ] エラー率トラッキング・アラート

**SEO**

- [x] Core Web Vitals / 内部リンク / Search Console 基本設定
- [ ] Search Console 定期レビュー（カバレッジ・パフォーマンス）

**PageSpeed / フロントエンド（詳細は [`PERFORMANCE.md`](PERFORMANCE.md)）**

- [x] フェーズ1: JS defer / フォント軽量化 / Cache-Control 修正 / 不要 CSS 除去（デプロイ・PSI 確認は未）
- [x] フェーズ2: Font Awesome サブセット / SSR 済み API スキップ / Bootstrap 自前ホスト（デプロイ・PSI 確認は未）
- [ ] フェーズ3: 非アクティブタブ遅延レンダリング / DOM 削減
- [ ] PSI スコアの定期記録（`PERFORMANCE.md` スコア表）

### 優先度: 中

- [x] API レート制限（主要マネージャー）
- [ ] キャッシュ: カテゴリ別 TTL / 部分更新 / ヒット率
- [ ] テスト: ユニット・統合・API 詳細（現状は基本 UI のみ）

### 優先度: 低

- [ ] パフォーマンス監視（API / DB / ページロード）
- [ ] セキュリティ: API キー暗号化 / IP レート制限 / CORS 見直し
- [ ] ドキュメント: OpenAPI / 開発者ガイド拡充
- [ ] CI/CD: 自動テスト・デプロイ・品質チェック強化

---

## 決定ログ・KPI

### 合格ライン（マネタイズ）

| 指標 | 目標 | 達成 |
|------|------|------|
| Waitlist（JP・4週） | 50 | [ ] |
| 有料会員（初期限定） | 10 | [ ] |
| 主観品質（4週平均） | ≥ 3.5 | [ ] |
| フェーズ1 欠配（4週） | 0 | [ ] |

### 週次メモ

| 日付 | メモ |
|------|------|
| 2026-06-22 | `todo.md` + `monetization.md` を本 BACKLOG に統合。1536MB 安定・retention purge デプロイ済。 |
| 2026-06-26 | PageSpeed 改善の進捗管理を `docs/PERFORMANCE.md` に分離。BACKLOG からリンク。 |
| | |

### 決定ログ

| 日付 | 決定内容 |
|------|----------|
| 2026-06-11 | マネタイズ本命案 A、並行 B 可。 |
| 2026-06-19 | フェーズ2a: teaser / Waitlist / GA4。 |
| 2026-06-21 | OOM 対策: subprocess + 1536MB。サブカテゴリ全取得維持。 |
| 2026-06-22 | 将来 To Do を `docs/BACKLOG.md` に一本化。 |
| | |

### KPI（週次記録用）

| 指標 | 意味 |
|------|------|
| Waitlist 登録（JP/US） | 関心の規模 |
| Fake door CTR | click / view |
| 有料転換 | 初回課金・継続 |
| `approved` 率 | 配信可能原稿 |
| 欠配・遅延 | パターンA SLA |
| 主観品質 1〜5 | 週平均 |

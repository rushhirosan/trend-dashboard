# Backlog — 今後の To Do 集約

**このファイルが将来の改善・拡張・商品化タスクの正本です。**  
方針変更・ステップ完了・新規課題はここだけを更新する（ルート `todo.md` / 旧 `monetization.md` は使わない）。

**更新ルール**

- 完了 → 該当 `[ ]` を `[x]` に
- 方針変更 → [決定ログ](#決定ログ) に1行
- 週次の数値 → [週次メモ](#週次メモ)
- 日次サマリー品質・SLA の詳細手順 → [`summary_pattern_a_phase1.md`](summary_pattern_a_phase1.md)

**最終更新:** 2026-09-12（課金お試し = PAY.JP **API v2・ワンショット（JP・約30日）**。月額定期は後続）

---

## 目次

1. [いまフォーカスするもの](#いまフォーカスするもの)
2. [次にフォーカスするステップ](#次にフォーカスするステップ)
3. [AIサマリー・マネタイズ](#aiサマリー・マネタイズ)
4. [プラットフォーム・運用](#プラットフォーム・運用)
5. [ソース・API 拡張](#ソースapi-拡張)
6. [プロダクト・品質改善](#プロダクト品質改善)
7. [決定ログ・KPI](#決定ログkpi)

### 有料コンテンツのドキュメント分担

| ファイル | 役割 |
|----------|------|
| **`docs/BACKLOG.md`（本ファイル）** | 商品化の方針・線引き・ロードマップ・進捗チェックリスト・決定ログ |
| [`summary_pattern_a_phase1.md`](summary_pattern_a_phase1.md) | 配信 SLA・品質チェックリスト・コピペ用テンプレ |
| [`summaries/README.md`](summaries/README.md) | 原稿の命名・レビュー gate（`draft` / `approved`）・保持期間 |

---

## いまフォーカスするもの

| 領域 | 状態 | 次のアクション |
|------|------|----------------|
| **課金入り口（2b）** | **PAY.JP v2 Checkout お試し実装済**（JP・約30日・クレカ/PayPay）。本番申請・secrets が次 | **次:** セキュリティ申告・PayPay 審査 → Fly secrets + Webhook → お試し購入1人 → 有料メール確認 |
| **AIサマリー配信** | 日次・週次とも GHA → 自分宛 dogfood が安定。有料送信は dogfood の後（`--from-api`） | 購読者 API は本番済。決済接続後に本番購読者を載せる |
| **定時取得** | 1536MB で JP/US 安定 | Grafana OOM アラート（任意・後回し可） |
| **データ保持** | DB / 原稿 10日・週次30日 purge 実装済 | 変更なし |

---

## 次にフォーカスするステップ

dogfood 配信は回っている。GHA 有料送信・購読者 API は用意済み。

**課金戦略（2026-09-12）:** Stripe は使わない。いまは **PAY.JP API v2 のワンショットお試し**（JP・約30日・¥300〜500 案）で「払う人がいるか」を見る。PayPay / Apple Pay は v2 都度払いとして候補。**月額自動（v1 Subscription / 将来の自前定期）は後続。** note は課金導線に使わない（書きたい記事用）。

### 本線 — フェーズ2b 残り（この順で）

| # | タスク | 状態 | やること |
|---|--------|------|----------|
| 1 | **有料配信 GHA 連携** | 済 | dogfood の後に `--from-api`。購読者 API は 2026-08-19 デプロイ済 |
| 2 | **PAY.JP v1 定期（クレカ）** | ローカル済・本番後回し | Plan + token + Subscription。ローカル E2E で DB 登録確認済。3DS・セキュリティ申告が本番ブロッカー |
| 3 | **お試し商品の定義** | 方針決定 | **ワンショット約30日 / ¥300〜500 / JP のみ / 自動更新なし**。日次＋期間内の週次 |
| 4 | **PAY.JP API v2 都度払い** | 実装済（次は申請） | Checkout v2 hosted。クレカ＋PayPay。Webhook `checkout.session.completed` → 購読者登録 |
| 5 | **セキュリティ申告・本番申請** | 未（次） | 加盟店の義務申告（v1/v2 共通）。PayPay は別途審査。3DS は v2 Checkout 側で対応 |
| 6 | **DB: お試し期限** | 実装済 | `expires_at` で配信対象から除外。期限後は再購入 |
| 7 | **Fly secrets + Webhook** | 未 | `PAYJP_*`（v2 用鍵）+ Webhook URL + 金額/日数/支払い方法 |
| 8 | **本番お試し購入 → 有料メール** | 未 | 1人で30日配信とメール受信を確認 |

10人・継続率は入り口の条件ではない。お試しで温度を見てから月額自動を検討。

### 2b 最小セット — 進捗（実装チェック）

- [x] **決済（v1 定期）** — ローカル E2E 済（コード資産）。**いまの販売入口には使わない**
- [x] **決済（v2 お試し）** — Checkout v2 都度払いワンショット（約30日）。JP のみ。クレカ＋PayPay（審査後）
- [x] **有料配信リスト** — `ai_summary_subscribers`（email, region_plan, is_active, `payjp_*`, `expires_at`）
- [x] **有効期限** — `expires_at` 超過は配信スキップ（`list_*_active`）
- [x] **送信スクリプト** — `send_summary_paid_email.py` + GHA `--from-api`
- [x] **UI** — 「お試し30日」+ Checkout リダイレクト（クレカ / PayPay）
- [ ] **有料メール受信確認** — お試し購入者1人 + GHA

### 並行 — コンテンツ改善（課金の後でも可）

- [ ] 日次: teaser 切れ・「昨日の注目」の選び方・横断の出し方
- [ ] 週次: 日次の寄せ集めにしない（流れ・ホット・週内の実動）
- [ ] 有料化前に欲しい欠損明記（`missing_sources` / 短縮テンプレ）は、初回課金の後でも可。購読 UI の免責文言は v2 お試し実装時に載せる

### この段階ではやらない

- Waitlist 本番オープン / JP 50件
- `draft` → `approved` の自動ゲート（dogfood は draft 送信のまま）
- Web プレビュー公開（フェーズ3）
- 既存 Subscription UI（`ENABLE_SUBSCRIPTION_UI`）の復活
- note / Substack を **課金導線** にする（note は書きたい記事用。課金箱にしない）
- US / both の自サイト課金
- **月額自動の本番公開**（お試し需要が見えてから。3DS 込み）
- 決済の日数単位の期間延長 / 欠配1回ごとの自動返金 / 利用規約ページ（特商法の最低表示はお試し公開時に検討）

---

## AIサマリー・マネタイズ

トレンドダッシュボードの **AI日次／週次サマリー** を商品化する計画。

### プロダクトの位置づけ

| レイヤー | 役割 | 課金 |
|---------|------|------|
| **ダッシュボード** | 複数ソースの生トレンド（JP/US） | **無料**（集客・信頼の入口） |
| **AIサマリー** | 順位の動き・カテゴリ横断・昨日の注目 | **有料候補** |
| **X 20時投稿** | 急上昇3件のティーザー | **停止（2026-07）— 使用していない** |

- 原稿: [`docs/summaries/`](summaries/README.md)（**サイト未公開** — フェーズ3でプレビューのみ公開予定）
- 品質・配信 SLA: [`summary_pattern_a_phase1.md`](summary_pattern_a_phase1.md)
- Fake door / 購読 CTA: `templates/partials/ai_summary_fake_door.html`, `ai_summary_checkout_form.html` / CTA: `summary_email_cta.html`（初版は **JP のみ**。Waitlist フォームオフ）
- Waitlist API は実装済みだが **本番登録は止めたまま**（`data-waitlist-enabled="false"`）。課金入り口では使わない
- 送信: **Resend**（検証・GHA dogfood・本番で共通）。Gmail SMTP はフォールバックのみ
- **本命案:** A（フリーミアム + メール）。note は課金導線にしない
- **決済:** Stripe は許可をもらえず終了。**いまのお試し = PAY.JP API v2 ワンショット（JP・約30日）。** 月額自動は後続。US は後続プロバイダ

### 地域プラン（JP / US / 両方）

有料メールは **地域ごとに別原稿**（`docs/summaries/daily/` vs `daily/us/`、週次も同様）。配信オプションとしての `region_plan` は次の3値。

| `region_plan` | 配信内容 | 日次の通数 | 週次の通数 | お試し課金 |
|---------------|----------|:----------:|:----------:|:----------:|
| **`jp`** | 日本向けサマリー全文のみ | 1 | 1 | **対象** |
| **`us`** | US 向けサマリー全文のみ | 1 | 1 | 後続 |
| **`both`** | JP + US の両方 | 2 | 2 | 後続 |

- ダッシュボード上の地域タブ（JP/US）と **同じ言語・同じ原稿** をメールする（JP=日本語、US=英語）
- **`both` は1通にまとめない** — 読みやすさと件名の明確さのため、地域ごとに別メール（dogfood と同じ分割）
- 有料リスト: `email`, `region_plan`, `payjp_*`, `is_active`, **`expires_at`（お試し用・追加予定）**, `created_at`
- **いまの販売:** PAY.JP **v2 都度払い**ワンショット。約 **30日** / **¥300〜500**（仮）/ 自動更新なし / `region_plan=jp`
- **後続の本線候補:** クレカ月額自動（v1 Subscription 資産 or v2 自前定期）+ EMV 3-Dセキュア
- PayPay / Apple Pay: v2 都度払いとしてお試しに載せられる（定期には使えない）

**UI（お試し・PAY.JP v2）案**

```
日本のサマリーお試し（約30日・日次＋週次）— ¥300〜500・自動更新なし
[ 購入する ] → PAY.JP v2（クレカ / 検討: PayPay）→ 成功後に配信開始
```

US / both は出さない。

### コンテンツ線引き（案1: ティーザー公開 — 採用方針）

**同じ原稿（`docs/summaries/`）を、Web はプレビュー・メールは全文** に分ける。別文章を書く必要はない。

| 提供形態 | 対象期間 | 内容 | 課金 |
|----------|----------|------|------|
| **ダッシュボード** | 現在に近い生データ | 表・タブ（既存） | 無料 |
| **Web プレビュー** | **過去**の観測結果（日次=観測日、週次=先週 ISO 週） | 下表のプレビュー範囲 | 無料（GEO・集客） |
| **メール全文** | 同上 | プレビュー + カテゴリ別詳細 + 横断（該当時）+ 週次は週内推移 | 有料候補 |

**公開タイミングのイメージ**

- 日次: 観測日 D のスナップショットが揃い、**D+1 朝**に生成（06:50 前後）→ 全文は **7:30 JST 目標**
- 週次: 先週 W1 を **翌週月曜 W2 朝**に生成（07:30 前後）→ 全文は **月曜 8:00 JST 目標**
- 表現は「今日のサマリー」ではなく **「昨日のトレンドまとめ」「先週のトレンドまとめ」**（観測日・生成日時を明示）。ユーザー向け文言に「出勤前」「メールです」は使わない

#### 日次: プレビュー vs 全文

| セクション（原稿 md） | Web プレビュー | メール全文 |
|----------------------|:--------------:|:----------:|
| 昨日の注目（旧: 一行結論） | ○ | ○ |
| 昨日いちばん動いた3つ（出典・順位推移） | ○ | ○ |
| 複数ソースで重なった話題 | ✕ | ○（該当時のみ） |
| カテゴリ別トップ3（ニュース / 検索・動画 / テック / エンタメ・ショッピング 等） | ✕ | ○ |
| 観測日・生成時刻・スロット | ○ | ○ |

#### 週次: プレビュー vs 全文

| セクション（原稿 md） | Web プレビュー | メール全文 |
|----------------------|:--------------:|:----------:|
| 先週の流れ（JP / US 短文） | ○ | ○ |
| 先週いちばん動いた話題（実動のみ） | ○ | ○ |
| 週のホットトピック | ✕ | ○ |
| 来週に残る論点 | ✕ | ○ |
| カテゴリ別 top3（JP / US × 各カテゴリ） | ✕ | ○ |
| 週内の順位推移（`06-29 (2位) → …`） | ✕ | ○ |
| 対象週・生成時刻 | ○ | ○ |

週次プレビューは日次より **さらに絞る**（流れ + 動いた話題各1件）。カテゴリ網羅と週内推移はメールの核。

#### Web 公開 UI/UX（初期）

- **ヘッダーに「サマリー」は出さない**（ダッシュボードの軽さを維持）
- トップの既存サマリーカードからのみ導線: **「プレビューを読む」**（フェーズ3） / **「お試し購入」**（2b は PAY.JP v2・JP 固定。Waitlist は使わない）
- URL 案:
  - `/summaries/daily/YYYY-MM-DD` — 日次プレビュー（`status: approved` のみ）
  - `/summaries/weekly/YYYY-Www` — 週次プレビュー（後追い可）
  - `/summaries` 一覧 — **後回し可**（まず直近1本へのリンクだけでも可）
- 保持: 日次 **10日**・週次 **30日**（git purge と揃える）→ 公開 URL もローリング
- GEO 補助: `/llms.txt`（固定1ファイル、サマリー URL を記載）

**実装順（案）:** `llms.txt` → 日次プレビュー1ルート → トップカードからリンク → 週次・一覧

#### 有料メールの障害・欠損時の扱い

完全配信は約束しない。時刻は **目標**（保証ではない）。**欠損時の透明性** と、重大欠配時の **手動救済** を商品仕様にする。

お試し期間中は重大欠配時に **全額返金（手動）** を既定にする。月額自動に移ったら **翌月無料 or 返金**。日数単位の期間延長 API は使わない。

| 状況 | 対応 |
|------|------|
| 一部ソース欠損 | 欠配ではない。メール冒頭に明記し **短縮版** を送る（件名 `[一部欠損]` 可） |
| 主要カテゴリの半分以上欠損 | 短縮版。期間内累計の判断材料 |
| 日次メール **完全欠配** 1回 | 復旧後に遅延配信を試みる。課金は触らない（お詫びのみ） |
| 週次メール **完全欠配**、または期間内の日次欠配が複数 | PAY.JP 管理画面等で **全額返金**（月額期は翌月無料も可） |
| ダッシュボード全体障害 | 復旧後に再生成・再送。送れなければ上の重大欠配と同じ |
| 週次で日次が欠けている | 対象日を明記して週次を出す or 週次を遅延 |
| 受信側（迷惑メール・アドレス誤り） | 再送のみ。課金は触らない |

**商品文言（お試し UI / 成功ページ）:** 配信は目標時刻（日次 **7:30** / 週次月曜 **8:00**、遅延上限あり）。外部データ・生成処理により欠損・遅延・欠配がありうる。重大な欠配は返金。メール環境による未到達は保証しない。

**2b ではやらない:** 欠配1回ごとの自動返金、期間延長 API、利用規約ページ（特商法の最低表示はお試し公開時に検討）。

**有料化前に欲しい仕組み（未実装）**

- [ ] 生成結果に `missing_sources` / `partial_sources` を持たせる
- [ ] 欠損時の短縮メールテンプレ
- [ ] 送信成功/失敗ログ・再送キュー

### ロードマップ

```
フェーズ1  原稿生成・dogfood 配信（課金なし）← 運用として到達
    ↓
フェーズ2a  Fake door + Waitlist 実装 ← 実装済み。本番登録は開かない
    ↓
フェーズ2b  課金入り口 → 限定有料 ← いまここ（PAY.JP v2 お試しワンショット。GHA 有料配信は用意済）
    ↓
フェーズ3   サイト内プレビュー + 有料配信の自動化
```

**フェーズ1 → 2b:** 正式な4週記録シートは未着手。dogfood（日次・週次）が安定して届いていることをもって 2b に進む。**2b の完了判定**は「お試し購入者に GHA から有料メールが届く」こと。

### 進捗チェックリスト

#### フェーズ1 — 原稿・品質（課金前）

dogfood は `draft` のまま自分宛に送っている。公開・有料の approve ゲートは後回し。

**1-1 日次**

- [x] GHA `ai-daily-summary.yml` 稼働
- [x] `docs/summaries/daily/` 蓄積
- [x] 直近の retention 窓で意図しない欠配なし（生成+dogfood。2026-08 時点で日次が連続）
- [ ] 失敗時再生成手順を1回以上実施

**1-2 週次**

- [x] GHA `ai-weekly-summary.yml`
- [x] `docs/summaries/weekly/` に週次あり（2026-08 時点で W30–W33 が連続）
- [ ] 直近2週が「日次羅列」でない（人レビュー・改善継続）

**1-3 レビューゲート** — 課金入り口より後回し

- [ ] draft → approved 運用合意
- [ ] サンプル1本以上 `status: approved`
- [ ] 毎日チェックリストを回した記録

**1-4 SLA・品質記録** — 正式シートは未着手。dogfood 安定で 2b に進む

- [ ] 記録シート開始（任意。課金後の欠配監視に使う）
- [ ] 4週分の品質・欠配記録 → 出口判定（2b のブロッカーにしない）

**1-5 X との役割分担**

- [x] ~~夜=X 急上昇 / 朝=AIサマリー~~ — 設計時のみ。**X 系列は 2026-07 停止**（GHA 削除・Discord・スケジューラ連携なし）
- [ ] ~~X 文案とダッシュ CTA の文言統一~~ — **対象外**（Daily X post series 使用していない）

#### フェーズ2a — Waitlist（課金なし）

実装済み。本番登録は開かず、課金入り口（2b）に進む。

- [x] 一行結論抽出・Fake door 実データ・Waitlist API/DB/UI
- [x] GA4 `fake_door_view` / `waitlist_*`
- [ ] ~~本番 Waitlist 登録 E2E~~ — **後回し**（フォームは `data-waitlist-enabled="false"`）
- [ ] ~~2〜4週: view / click / 登録数記録（目安 JP 50件）~~ — **後回し**（課金入り口の条件にしない）

#### フェーズ2b — 課金入り口 → 限定有料（案 A）

詳細は [次にフォーカスするステップ](#次にフォーカスするステップ)。

- [x] `ai_summary_subscribers` + 有料送信スクリプト + GHA `--from-api`
- [x] PAY.JP v1 定期: ローカル E2E 済（本番・3DSは後回し）
- [x] お試し商品: 約30日 / ¥500 既定（`PAYJP_TRIAL_*`）/ JP / 自動更新なし
- [x] PAY.JP **API v2** 都度払い（Checkout v2 hosted）+ Webhook `checkout.session.completed`
- [x] DB: `expires_at`（お試し期限）
- [x] UI: お試し購入 CTA（クレカ / PayPay）
- [ ] セキュリティ申告・本番申請（PayPay 審査含む）
- [ ] Fly: v2 用 `PAYJP_*` secrets
- [ ] お試し購入1人で有料メール受信確認
- [ ] （後続）月額自動 + 継続率

#### フェーズ3 — サイト内プレビュー + 配信自動化

- [x] `/llms.txt`
- [ ] `/summaries/daily/YYYY-MM-DD`（approved のみ・プレビュー範囲）
- [ ] トップサマリーカード → 昨日分プレビューへのリンク（ヘッダー nav は増やさない）
- [ ] `/summaries/weekly/YYYY-Www`（approved のみ・プレビュー範囲）
- [ ] `/summaries` 一覧（任意・後追い可）
- [x] sitemap に公開中のサマリー URL を反映
- [ ] 7:30 JST（日次）/ 月曜 8:00 JST（週次）自動配信 + 失敗アラート
- [ ] 週次バンドル同梱（メール全文）
- [ ] 欠損時短縮テンプレ + 件名 `[一部欠損]`

#### 並行検証（任意）

| 案 | 主な未完了 |
|----|-----------|
| **B** note/Substack | 媒体決定 → 5本投稿 → CTA + UTM |
| **C** B2B | 1枚提案 → サンプル配信 → 契約1件 |
| **D** 寄付 | BMC 本番 username / 特典ルール |
| **E** タイムボックス | 7:30 / 月8:00 を目標時刻として商品文に明記（昨日/先週）。出勤前とは書かない |

### マネタイズ案（参照）

| ID | 案 | 単価イメージ |
|----|-----|-------------|
| A | フリーミアム + メール | 月 ¥500〜980（JP / US / 両方 同額・Price 1本） |
| B | note / Substack | 月 ¥500〜 |
| C | B2B ブリーフィング | 月 ¥9,800〜 |
| D | Buy Me a Coffee | 任意 |
| E | タイムボックス約束 | A/B の SLA を SKU 化 |

2b の手順は [次にフォーカスするステップ](#次にフォーカスするステップ) が正。これ以上の手順書が必要になったら [決定ログ](#決定ログ) に1行足してから追記する。

### トラブル時

| 状況 | アクション |
|------|-----------|
| 品質が低い | レビュー強化 / `generate_ai_daily_summary.py` プロンプト |
| approved が間に合わない | 遅延可、draft は Web に出さない / 短縮テンプレ |
| Waitlist が伸びない | note 導線 / プレビュー CTA A/B |
| リンク大量死 | リンクチェック脚本検討 |
| 有料配信でデータ欠損 | [障害・欠損時の扱い](#有料メールの障害欠損時の扱い) に従う |

### 関連コード

| 種別 | パス |
|------|------|
| 日次 / 週次生成 | `scripts/generate_ai_daily_summary.py`, `generate_ai_weekly_summary.py` |
| Fake door | `templates/partials/ai_summary_fake_door.html`, `static/js/ai-summary-fake-door.js` |
| Waitlist | `routes/waitlist_routes.py`, `services/waitlist/` |
| **有料サマリー（課金）** | `routes/billing_routes.py`, `services/billing/`（**v2 Checkout お試し** + v1 定期は後回し）, `static/js/ai-summary-checkout.js` |
| **有料メール送信** | `scripts/send_summary_paid_email.py`, `services/summary/summary_paid_email.py`, GHA `ai-*-summary.yml`（dogfood の後、`--from-api`） |
| 購読者 API | `GET /api/billing/ai-summary/subscribers`（`SUMMARY_UPSERT_TOKEN`。GHA は DB 直結しない） |
| 購読者 DB | `services/billing/ai_summary_subscriber_manager.py` → テーブル `ai_summary_subscribers` |
| サブスク（休眠・無料メール登録） | `services/subscription/`, `ENABLE_SUBSCRIPTION_UI` — **課金には使わない** |
| dogfood メール | `scripts/send_summary_dogfood_email.py`, `services/summary/summary_dogfood_email.py`, GHA `ai-*-summary.yml`（Resend） |
| ローカル DB 確認 | `psql -h localhost -U hiroyuki_igusa_2025 -d trends_db` → `SELECT * FROM ai_summary_subscribers;` |

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
- [x] `docs/summaries` 日次10日・週次30日 purge（DB: 03:00 JST / git: GHA `summary-retention-purge.yml`）
- [x] GHA 日次サマリー欠走: Fly **08:15 JST** に `summary_documents` 存在チェック、無いときだけ Discord（生成・メールしない）
- [x] GHA 日次/週次: 手動後の遅延 cron で二重メールしないよう、DB に jp+us があれば生成・メールをスキップ（`force` で再生成可）
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
- [x] トップ head のみ強化（title/OG・`llms.txt` link）。**ダッシュボード body / UI は変更しない**
- [x] `/about` FAQ + FAQPage スキーマ・G7 役割分担文言
- [x] `/llms.txt` に直近サマリー実 URL を動的掲載
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
| Waitlist（JP・4週） | 50 | [ ] 後回し（2b の条件にしない） |
| 有料会員（初期限定） | 10 | [ ] 入り口後の目標 |
| 主観品質（4週平均） | ≥ 3.5 | [ ] 課金と並行 |
| フェーズ1 欠配（dogfood） | 直近窓で0 | [x] 2026-08 の日次・週次が連続 |

### 週次メモ

| 日付 | メモ |
|------|------|
| 2026-06-22 | `todo.md` + `monetization.md` を本 BACKLOG に統合。1536MB 安定・retention purge デプロイ済。 |
| 2026-06-26 | PageSpeed 改善の進捗管理を `docs/PERFORMANCE.md` に分離。BACKLOG からリンク。 |
| 2026-07-12 | 案1（Web プレビュー + メール全文）・GEO 公開方針・障害時 SLA を BACKLOG に追記。 |
| 2026-07-29 | SEO/GEO: トップ UI 非接触で head・llms.txt・about FAQ のみ強化。 |
| 2026-08-18 | dogfood（日次・週次・Resend）安定。Waitlist は開かず、課金入り口（自サイト定期課金）を次の本線にする。 |
| 2026-08-18 | 有料メールは **JP / US / 両方** の3プラン（配信オプション）。価格は共通・`region_plan` で配信のみ出し分け。 |
| 2026-08-18 | 有料配信リスト `ai_summary_subscribers` と購読 UI の初版を用意。重大欠配の救済は翌月無料/返金。 |
| 2026-08-19 | GHA 有料配信を dogfood の後に追加。購読者は `GET /api/billing/ai-summary/subscribers`（`SUMMARY_UPSERT_TOKEN`）。DATABASE_URL は GHA に置かない。 |
| 2026-09-12 | **Stripe は許可をもらえなかった**ため課金には使わない。本線候補は **PAY.JP（JP）**。US は後続。 |
| 2026-09-12 | **お試しは PAY.JP API v2・ワンショット（約30日 / ¥300〜500 案 / JP）。** v1 定期はローカル検証済だが本番は後回し。PayPay は都度払い候補。note は課金に使わない。 |

### 決定ログ

| 日付 | 決定内容 |
|------|----------|
| 2026-06-11 | マネタイズ本命案 A、並行 B 可。 |
| 2026-06-19 | フェーズ2a: teaser / Waitlist / GA4。 |
| 2026-06-21 | OOM 対策: subprocess + 1536MB。サブカテゴリ全取得維持。 |
| 2026-06-22 | 将来 To Do を `docs/BACKLOG.md` に一本化。 |
| 2026-07-12 | **案1 採用**: Web=プレビュー（過去分・approved のみ）、メール=全文。初期はヘッダー nav 増やさずトップカードから導線。週次も別 URL でプレビュー/全文を分離。有料時は欠損明記・短縮配信・重大欠配はクレジット/返金。 |
| 2026-07-25 | サマリー配信はまず **dogfood（自分宛・draft・生成直後・JP/US 日次+週次）** で2週間品質確認。問題なければ自動 approve へ。送信は **Gmail SMTP**（SendGrid Trial 切れのため）。 |
| 2026-08-09 | 日次メール全文に **読み方（編集メモ）** を追加（Web プレビュー非表示）。有料差はリスト増より事実のつなぎ方。 |
| 2026-08-10 | 日次カテゴリ名を **エンタメ・ショッピング** に変更（楽天等の違和感解消）。読み方メモは土日にマーケット静けさを材料にしない。 |
| 2026-08-11 | 読み方（編集メモ）は **要る日だけ**（横断・静けさ等）。「横断なし」「カテゴリ分散」だけの空読みは JP/US とも出さない。 |
| 2026-08-12 | 日次の **読み方（編集メモ）** を廃止。横断は専用セクション、静けさ・一過性メモは価値が薄いため。 |
| 2026-08-18 | **2b に進む。** 課金入り口は自サイト定期課金 + 有料配信リスト + Resend。既存 Subscription UI は使わない。Waitlist 50 / 自動 approve / Web プレビューは後回し。中身改善は並行。 |
| 2026-08-18 | 有料メールの **地域プラン**: `jp` / `us` / `both`（両方は日次・週次それぞれ2通）。価格共通 + DB に `region_plan`。 |
| 2026-08-18 | 有料配信リスト `ai_summary_subscribers` + 地域プラン付き購読 UI の初版。 |
| 2026-08-18 | 配信目標を **出勤前チェック**向けに変更: 日次 **7:30**（上限8:00）/ 週次月曜 **8:00**（上限8:30）。10:30/11:00 は廃止。 |
| 2026-08-18 | **2b の残り:** GHA に `send_summary_paid_email.py`、commit/deploy、本番決済接続。有料メール受信が 2b 完了の判定。 |
| 2026-08-18 | **配信は目標であり保証しない。** 日次欠配1回は課金を触らない。週次欠配 or 月内の日次複数欠配は翌月無料 or 返金。受信側未到達は対象外。期間延長 API は使わない。 |
| 2026-08-19 | 有料配信の GHA は **DB 直結しない**。本番アプリの購読者 API + ワークスペースの Markdown + Resend。 |
| 2026-08-19 | ユーザー向け文言から **「出勤前」「メールです」を外す**。時刻は目標のみ。課金受付開始は決済 secrets を本番に入れたとき。 |
| 2026-08-27 | GHA 日次欠走は Healthchecks 等を増やさず、Fly 08:15 JST で `summary_documents` を見る。成功日は SELECT のみ。無いとき Discord。 |
| 2026-08-27 | 手動 Run + 遅延 cron の二重メールは、GHA 先頭で DB 存在確認してスキップ。再生成は workflow_dispatch `force`。 |
| 2026-09-12 | **Stripe は許可をもらえなかった**ため使わない。PAY.JP（JP）を決済候補に。US/both 自サイト課金は後回し。 |
| 2026-09-12 | **お試し実装:** PAY.JP Checkout v2 hosted（`card,paypay`）+ `expires_at`。本番は申告・secrets・購入確認が残。 |

### KPI（週次記録用）

| 指標 | 意味 |
|------|------|
| Waitlist 登録（JP/US） | 関心の規模 |
| Fake door CTR | click / view |
| 有料転換 | 初回課金・継続 |
| `approved` 率 | 配信可能原稿 |
| 欠配・遅延 | パターンA SLA |
| 主観品質 1〜5 | 週平均 |

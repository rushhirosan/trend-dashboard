# Todo List

## 残課題 📝

### Reddit API関連
- [ ] Reddit API申請結果を待つ（通常1-2週間）
  - 申請日: 2025年11月22日
  - 申請内容: `/docs/REDDIT_API_APPLICATION_IMPROVED.md` に詳細記載
  - 参考: https://redditinc.com/ja-jp/policies/developer-terms

- [ ] Reddit代替API実装（再申請が却下された場合）
  - [ ] Dev.to APIの調査・実装
    - Dev.to APIドキュメント確認: https://developers.forem.com/api
    - Dev.to APIキー取得（必要に応じて）
    - Dev.toトレンド記事取得機能の実装
    - データベースキャッシュ機能の実装
    - フロントエンド表示機能の実装
  - その他の代替案（Dev.toが使えない場合）
    - Product Hunt API
    - GitHub Trending（スクレイピング）
    - Mastodon API

## OOM / スケジューラ（2026-06-21 調査） 🔥

### スナップショット履歴から分かったこと（`captured_at` → JST）

定時取得が成功している日（例: business_day **2026-06-19**）の目安:

| slot | 期待 (JST) | 実際の captured_at (JST) |
|------|------------|---------------------------|
| 07 | ~07:00 台 | ~07:12 |
| 13 | ~13:00 台 | ~13:12 |
| 19 | ~19:00 台 | ~19:12 |
| 01 | ~01:00 台（翌暦日） | ~01:12 |

**business_day=2026-06-20**（OOM 発生夜）:

| slot | captured_at (JST) | 判定 |
|------|-------------------|------|
| 07 | **~16:02** | ❌ 定時ではない（13 時台と同一セッション） |
| 13 | **~16:03** | ❌ 定時ではない（07 と 14 秒差で一括書き込み） |
| 19 | ~20:22 | △ 19 時台だが通常より ~1h 遅め（要ログ照合） |
| 01 | なし | ❌ 1:00 / 1:35 gap_retry とも OOM で未保存 |

→ 「6/20 の 07/13/19 は全部ある」は**定時成功ではなく、落ちた後のキャッシュ/backfill で穴埋めされた可能性が高い**（07/13 は同一時刻の一括補填が確定）。

確認コマンド（本番 API）:

```bash
curl -s "https://trends-dashboard.fly.dev/api/summaries/daily-snapshots?business_day=2026-06-20" \
  | python3 -c "import json,sys; from collections import defaultdict; d=json.load(sys.stdin); b=defaultdict(set); [b[r['slot']].add(r['captured_at']) for r in d.get('data',[])]; print({k:sorted(v) for k,v in b.items()})"
```

DB 直確認: `scripts/inspect_scheduler_slots.py`（`scheduler_slot_run` + snapshots）。fly ssh 時は `PYTHONPATH=/app` が必要。

### 対策 TODO（メモリ増なし優先）

#### 即時（運用）

- [ ] **slot 01 補完**: `python scripts/backfill_snapshot_slot.py --slot-key 1am_2026-06-21`（OOM 後にキャッシュが生きていれば軽量。ダメなら 2048MB 一時 scale 後に gap_retry / 手動 refresh）
- [ ] **6/20 の 07/13 スナップショットを要再取得か判断**: captured_at が 16:02 JST のため AI 日次サマリー用の「その時点のトレンド」としては欠陥。必要なら `--slot-key 7am_2026-06-20` / `1pm_2026-06-20` を定時相当データで再 backfill（全量 refresh または当該スロットのみ）
- [ ] **Grafana で 6/20 07/13/19/21 1:00 の OOM・scheduler 完了ログを突合**（`Out of memory` / `refresh_all_trends` / `スナップショット保存` / `gap_retry`）

#### コード（優先度高 — 1024MB のまま完走を目指す）

- [ ] **スケジューラ全量 refresh から KKJ を外す or 別ジョブ化**（OOM 直前が KKJ レート待ち。ダッシュボード必須でなければ scheduler 負荷から除外）
- [ ] **scheduler 実行時のみ `fetch_all_categories=False`**（楽天・はてな・Note — 定時は軽量、手動/API は現状維持）
- [ ] **IPA RSS: 240 件一括 parse を limit 件に切る**（force_refresh 時もエントリ上限）
- [ ] **JP / US を同一プロセスで連続実行せず、フェーズ間にプロセス再起動 or ジョブ分割**（ピーク RSS 860MB 問題の根本）
- [ ] **captured_at 健全性チェック**: 保存時に slot 期待時刻帯（例: 07 なら 06:30–08:00 JST）外なら Discord warning（backfill 誤認防止）
- [ ] **`inspect_scheduler_slots.py` を fly ssh からそのまま実行可能に**（`sys.path` / `TODAY` 引数化）

#### 監視

- [ ] **memory_watchdog が OOM 前に Discord を出せていない理由を確認**（45s 間隔・82% 閾値 vs 861MB 瞬間到達）
- [ ] **Grafana アラート**: `Out of memory` / `Worker.*SIGKILL` で OOM 本体を通知（ロック回収アラートと役割分担）

#### 判断保留（最後の手段）

- [ ] **Fly VM 1024→2048MB の要否判断** — 差分 ~$5–6/月（~700–900 円）。上記コード対策後も 1am/7am で OOM が続く場合のみ
- [ ] 2048MB に上げる場合: `fly scale memory 2048 --app trends-dashboard` + `fly.toml` の `memory_mb` / `MEMORY_LIMIT_MB` を揃える

---

## 改善提案 🚀

### 優先度: 高

1. **エラーログとモニタリング**
   - [ ] 構造化ログの導入（JSON形式など）
   - [x] エラー通知機能（Discord Webhook） ✅
   - [ ] エラー率の追跡とアラート

2. **SEO対策**
   - [x] パフォーマンス最適化（Core Web Vitals） ✅
     - [x] CSS/JSの遅延読み込みとpreload設定
     - [x] 外部リソースのpreconnect/dns-prefetch
     - [x] キャッシュヘッダーの設定（静的ファイル1年、HTML5分）
   - [x] 内部リンク構造の改善 ✅
     - [x] フッターにサイトマップリンクを追加（全ページ）
     - [x] 各セクションにIDを追加（アンカーリンク対応）
     - [x] 主要ページ間の内部リンク強化
   - [ ] **Google Search Console セットアップ** ✅
     - [x] Google Search Consoleアカウントの作成
     - [x] サイトの所有権確認（HTMLタグ、DNS、Google Analytics連携など）
     - [x] sitemap.xmlの送信（`https://trends-dashboard.fly.dev/sitemap.xml`）
     - [x] robots.txtの確認（`https://trends-dashboard.fly.dev/robots.txt`）
     - [x] インデックス登録のリクエスト
     - [x] パフォーマンスレポートの確認
     - [x] カバレッジレポートの確認

### 優先度: 中

3. **APIレート制限** ✅
   - [x] 統一的なレート制限ユーティリティクラスを作成
   - [x] 各トレンドマネージャーにレート制限機能を追加（YouTube、Spotify、World News、Podcast、Stock、Crypto、Rakuten、Twitch、News、CNN、NHK、Hatena、HackerNews）
   - [x] Reddit、Qiita、Product Huntは既に実装済み

4. **キャッシュ戦略の最適化**
   - [ ] カテゴリ別のTTL設定
   - [ ] 部分更新機能（全データ再取得ではなく、差分更新）
   - [ ] キャッシュヒット率の追跡

5. **テストカバレッジ拡大**
   - [ ] ユニットテストの追加
   - [ ] 統合テストの追加
   - [ ] APIエンドポイントの詳細テスト
   - [ ] 現在は基本ページ/UIテストのみ

### 優先度: 低

6. **パフォーマンス監視**
   - [ ] API応答時間の追跡
   - [ ] DBクエリ時間の追跡
   - [ ] ページロード時間の追跡

7. **セキュリティ強化**
   - [ ] APIキーの暗号化
   - [ ] レート制限（IP単位）
   - [ ] CORS設定の見直し

8. **ドキュメント整備**
   - [ ] API仕様書（OpenAPI/Swagger）
   - [ ] 開発者ガイドの詳細化
   - [ ] デプロイ手順の詳細化

9. **CI/CDパイプライン**
   - [ ] 自動テスト実行
   - [ ] 自動デプロイ
   - [ ] コード品質チェック
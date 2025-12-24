# Todo List

## 進行中の課題 🔄

- [ ] Shopping Trendsのフィルタリング問題を調査（ログ確認）
- [ ] Hatenaデータベース接続の動作確認
- [ ] US版Podcast表示問題の修正（CSS/JavaScriptの根本原因調査）

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

## 改善提案 🚀

### 優先度: 高

1. **エラーログとモニタリング**
   - [ ] 構造化ログの導入（JSON形式など）
   - [ ] エラー通知機能（メール/Slack）
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
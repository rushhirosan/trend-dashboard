# テスト

## テスト方針

| 種別 | 目的 | ツール |
|------|------|--------|
| ユニットテスト | 個別関数・ロジックの検証 | pytest |
| 統合テスト | ページ・APIの基本動作 | test_pages.py |
| E2Eテスト | ブラウザでのUI確認 | test_ui.py (Selenium) |

## セットアップ

```bash
# 開発用依存関係をインストール
pip install -r requirements-dev.txt
```

## 実行方法

```bash
# 全テスト実行（pytest）
pytest tests/ -v

# カバレッジ付き
pytest tests/ -v --cov=. --cov-report=term-missing

# 特定テストのみ
pytest tests/test_ebay_affiliate.py -v

# 本番環境のページ/APIテスト
python tests/test_pages.py

# UIテスト（Selenium要）
python tests/test_ui.py
```

## テスト一覧

### test_ebay_affiliate.py（ユニット）
- eBay EPN アフィリエイトURL生成（campid/mkrid）
- 後方互換（EBAY_AFFILIATE_ID）
- 未設定時のフォールバック

### test_pages.py（統合）
本番URLへHTTPリクエストし、ステータス・コンテンツを検証。

- **ページ**: `/`, `/us`, `/data-status`, `/subscription/`
- **API**: 各種トレンドAPI

### test_ui.py（E2E）
Seleniumでブラウザを起動し、UI要素の存在を確認。

### test_scheduler_email.py
スケジューラーのメール送信（要確認プロンプト）。

## カバレッジ目標

- 現状: 部分的（trends関連の主要ロジックを優先）
- 方針: 新規・変更時に該当テストを追加し、段階的に拡充


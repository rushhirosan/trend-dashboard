# Amazon Best Sellers セットアップガイド

Amazon Best Sellersのデータを取得するには、非公式のRSSサービス（AmaranRSS等）を使用します。

## 📋 前提条件

- AmaranRSSなどのサービスアカウント（必要に応じて）
- Amazon Best SellersページのURL

## 🚀 セットアップ手順

### 1. Amazon Best SellersページのURLを準備

Amazon Best Sellersのページから、RSS化したいカテゴリのURLをコピーします。

例：
- 書籍: `https://www.amazon.com/Best-Sellers-Books/zgbs/books/`
- エレクトロニクス: `https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/`
- コンピュータ: `https://www.amazon.com/Best-Sellers-Computers-Accessories/zgbs/pc/`

### 2. AmaranRSSでRSS URLを生成

1. AmaranRSSのウェブサイト（例: https://www.livdir.com/amaranrss/）にアクセス
2. 上記で準備したAmazon Best SellersのURLをフォームに貼り付け
3. 「Generate」ボタンを押してRSS URLを生成
4. 生成されたRSS URLをコピー（例: `https://livdir.com/am-tb/xxxx.rss`）

### 3. 環境変数に設定

生成したRSS URLを環境変数 `AMAZON_RSS_URLS` に設定します。

#### ローカル環境（`.env`ファイル）

```bash
# 単一のRSS URL
AMAZON_RSS_URLS=https://livdir.com/am-tb/xxxx.rss

# 複数のRSS URL（カンマ区切り）
AMAZON_RSS_URLS=https://livdir.com/am-tb/xxxx.rss,https://livdir.com/am-tb/yyyy.rss
```

#### Fly.io環境

```bash
flyctl secrets set AMAZON_RSS_URLS="https://livdir.com/am-tb/xxxx.rss,https://livdir.com/am-tb/yyyy.rss"
```

### 4. 動作確認

環境変数を設定後、アプリケーションを再起動して動作を確認してください。

```bash
# ローカル環境
python app.py

# Fly.io環境
flyctl deploy
```

## ⚠️ 重要な注意事項

### レート制限

- **推奨**: 1時間に1回以上の取得は避けてください
- アプリケーション側で自動的に1時間に1回の制限が設定されています
- キャッシュ機能により、実際の外部API呼び出しはスケジューラー実行時（1日3回：7時、13時、19時 JST）のみです

### 非公式サービスについて

- Amazon公式が提供するものではありません
- サービスが停止する可能性があります
- 商用利用や大量取得には適していません
- ダッシュボードでの表示用途としては問題ありません

### エラーハンドリング

- RSS URLが設定されていない場合、エラーメッセージが表示されます
- RSS取得に失敗した場合、空のデータとして扱われます
- ログを確認して問題を特定してください

## 🔧 トラブルシューティング

### RSS URLが取得できない

1. AmaranRSSでRSS URLが正しく生成されているか確認
2. 生成されたRSS URLに直接アクセスして、RSSフィードが表示されるか確認
3. 環境変数が正しく設定されているか確認

### データが表示されない

1. アプリケーションのログを確認
2. `/api/amazon-trends?force_refresh=true` エンドポイントを直接呼び出して確認
3. RSS URLが有効か確認（期限切れの可能性）

## 📚 参考リンク

- [AmaranRSS](https://www.livdir.com/amaranrss/) - Amazon RSS生成サービス
- [Amazon Best Sellers](https://www.amazon.com/Best-Sellers/zgbs/) - Amazon Best Sellersページ


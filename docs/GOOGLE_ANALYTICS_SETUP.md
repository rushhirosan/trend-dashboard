# Google Analytics (GA4) セットアップガイド

## 概要

このプロジェクトでは、Google Analytics 4 (GA4) を使用してアクセス解析を行います。

## セットアップ手順

### 1. Google Analyticsアカウントでプロパティを作成

1. [Google Analytics](https://analytics.google.com/) にアクセス
2. アカウントを作成（まだの場合）
3. 「プロパティを作成」をクリック
4. プロパティ名を入力（例: "Trends Dashboard"）
5. レポートのタイムゾーンを選択（推奨: 日本時間）
6. 通貨を選択（推奨: 日本円）
7. 「作成」をクリック

### 2. データストリームを設定

1. 「データストリーム」をクリック
2. 「ウェブ」を選択
3. ウェブサイトのURLを入力: `https://trends-dashboard.fly.dev`
4. ストリーム名を入力（例: "Trends Dashboard Web"）
5. 「ストリームを作成」をクリック

### 3. 測定IDを取得

1. 作成したデータストリームをクリック
2. 「測定ID」をコピー（形式: `G-XXXXXXXXXX`）

### 4. 環境変数を設定

#### ローカル環境（.envファイル）

`.env`ファイルに以下を追加：

```env
GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX
```

#### 本番環境（Fly.io）

Fly.ioのシークレットとして設定：

```bash
fly secrets set GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX -a trends-dashboard
```

## 実装内容

- 全HTMLテンプレートにGA4のスクリプトを追加
- 環境変数`GOOGLE_ANALYTICS_ID`が設定されている場合のみスクリプトを読み込む
- 以下のページでトラッキングされます：
  - `/` (日本トレンドページ)
  - `/us` (USトレンドページ)
  - `/data-status` (データ鮮度情報ページ)
  - `/subscription` (サブスクリプションページ)

## 確認方法

1. 環境変数を設定後、アプリケーションを再起動
2. ブラウザでサイトにアクセス
3. ブラウザの開発者ツール（F12）で「Network」タブを開く
4. `gtag/js` へのリクエストが表示されれば正常に動作しています
5. Google Analyticsの「リアルタイム」レポートでアクセスを確認

## トラブルシューティング

### 「Internal error. Please try again」エラーが表示される場合

Google Analyticsを開くと「Internal error. Please try again」というエラーが表示される場合、以下の対処法を試してください：

1. **ページをリフレッシュ**
   - ブラウザでページをリロード（F5 または Cmd+R）

2. **ブラウザのキャッシュとクッキーをクリア**
   - Chrome: 設定 > プライバシーとセキュリティ > 閲覧履歴データの削除
   - キャッシュされた画像とファイル、Cookie を選択して削除

3. **シークレット/プライベートモードで試す**
   - 新しいシークレットウィンドウでGoogle Analyticsにアクセス

4. **ブラウザの拡張機能を無効化**
   - 広告ブロッカーやスクリプトブロッカーなどの拡張機能を一時的に無効化

5. **別のブラウザで試す**
   - Chrome、Firefox、Safariなど別のブラウザでアクセス

6. **Googleアカウントからログアウト/ログイン**
   - Googleアカウントから一度ログアウトし、再度ログイン

7. **時間を置いて再試行**
   - Google側の一時的なサーバーエラーの可能性があるため、数時間後に再試行

8. **Google Analyticsのステータスページを確認**
   - [Google Workspace Status](https://status.cloud.google.com/) で障害情報を確認

これらの対処法を試しても解決しない場合は、Googleのサポートに問い合わせることをおすすめします。

## 注意事項

- 環境変数が設定されていない場合、GAスクリプトは読み込まれません（エラーになりません）
- 測定IDは`G-`で始まる形式である必要があります
- データがGoogle Analyticsに反映されるまで数時間かかる場合があります
- Google Analyticsのダッシュボードでエラーが表示される場合、Google側の一時的な問題の可能性があります


# メール送信設定ガイド

## SendGrid（推奨）

### 1. アカウント作成
1. https://sendgrid.com/ にアクセス
2. 無料アカウントを作成
3. メール認証を完了

### 2. API Key作成
1. Dashboard → Settings → API Keys
2. "Create API Key" をクリック
3. 名前を入力（例: "trends_dashboard"）
4. 権限: "Full Access" または "Mail Send"
5. API Keyをコピー

### 3. 環境変数設定
```bash
export SMTP_SERVER=smtp.sendgrid.net
export SMTP_PORT=587
export SENDER_EMAIL=apikey
export SENDER_PASSWORD=your_sendgrid_api_key_here
```

### 4. 送信者情報設定
1. Settings → Sender Authentication
2. "Single Sender Verification" を設定
3. 送信者メールアドレスを登録
4. 確認メールを送信

## Mailgun

### 1. アカウント作成
1. https://www.mailgun.com/ にアクセス
2. 無料アカウントを作成

### 2. ドメイン設定
1. Dashboard → Domains
2. サンドボックスドメインを使用（テスト用）
3. または独自ドメインを追加

### 3. 環境変数設定
```bash
export SMTP_SERVER=smtp.mailgun.org
export SMTP_PORT=587
export SENDER_EMAIL=postmaster@your-domain.mailgun.org
export SENDER_PASSWORD=your_mailgun_password
```

## テスト用（実際には送信されない）

### Mailtrap
```bash
export SMTP_SERVER=sandbox.smtp.mailtrap.io
export SMTP_PORT=2525
export SENDER_EMAIL=your_mailtrap_username
export SENDER_PASSWORD=your_mailtrap_password
```

## 使用方法
1. 環境変数を設定
2. サーバーを再起動
3. サブスクリプション登録をテスト

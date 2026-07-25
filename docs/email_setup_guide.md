# メール送信設定ガイド

## Gmail SMTP（dogfood / 自分宛おすすめ・無料）

自分に日次・週次サマリーを送る用途ならこれが最短。

### 1. アプリパスワードを発行

1. Google アカウントで [2段階認証](https://myaccount.google.com/security) をオン
2. [アプリパスワード](https://myaccount.google.com/apppasswords) を作成（メール / その他）
3. 表示された 16 文字をコピー（スペースなしで `.env` に入れる）

### 2. `.env` 設定

```bash
EMAIL_PROVIDER=smtp
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=you@gmail.com
SENDER_PASSWORD=xxxxxxxxxxxxxxxx
SUMMARY_DOGFOOD_TO=you@gmail.com
```

### 3. 送信テスト

```bash
python scripts/send_summary_dogfood_email.py --kind daily --id 2026-07-22 --regions jp,us --dry-run
python scripts/send_summary_dogfood_email.py --kind daily --id 2026-07-22 --regions jp,us
```

### GitHub Actions

Repository secrets:

- `SENDER_EMAIL`
- `SENDER_PASSWORD`（アプリパスワード）
- `SUMMARY_DOGFOOD_TO`（省略可。未設定なら From と同じ扱い）

`ai-daily-summary` / `ai-weekly-summary` が生成直後に dogfood 送信する。

---

## SendGrid（任意・本番向け）

Trial 切れだと `Maximum credits exceeded` になる。有料枠があるときだけ。

```bash
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_FROM_EMAIL=your-verified-sender@example.com
SUMMARY_DOGFOOD_TO=your-verified-sender@example.com
```

または SMTP:

```bash
export SMTP_SERVER=smtp.sendgrid.net
export SMTP_PORT=587
export SENDER_EMAIL=apikey
export SENDER_PASSWORD=your_sendgrid_api_key_here
```

---

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
2. サーバーを再起動（またはスクリプトを再実行）
3. dogfood / サブスクリプション登録をテスト

# メール送信設定ガイド

検証（ローカル / dogfood / GHA）と本番は **同じ Resend** を使う。無料枠はおおよそ月 3,000 通・1日 100 通まで。

## Resend（推奨・検証と本番で共通）

### 1. ドメイン認証

Resend → Domains で `trends-dashboard.com` を追加し、DNS（DKIM / SPF）を verified にする。

### 2. API キー

Resend → API Keys で作成（送信だけなら **Sending access** で可）。表示された `re_...` は一度しか見られない。

### 3. ローカル `.env`

```bash
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxx
RESEND_FROM_EMAIL=noreply@trends-dashboard.com
SUMMARY_DOGFOOD_TO=you@gmail.com
```

### 4. Fly 本番（同じ変数）

```bash
fly secrets set \
  EMAIL_PROVIDER=resend \
  RESEND_API_KEY=re_xxxxx \
  RESEND_FROM_EMAIL=noreply@trends-dashboard.com \
  -a trends-dashboard
```

### 5. GitHub Actions（dogfood）

Repository secrets:

- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`（例: `noreply@trends-dashboard.com`）
- `SUMMARY_DOGFOOD_TO`（自分宛）

`ai-daily-summary` / `ai-weekly-summary` が生成直後に dogfood 送信する。

### 6. 送信テスト

```bash
python scripts/send_summary_dogfood_email.py --kind daily --id 2026-07-22 --regions jp,us --dry-run
python scripts/send_summary_dogfood_email.py --kind daily --id 2026-07-22 --regions jp,us
```

`EMAIL_PROVIDER=auto` のとき、`RESEND_API_KEY` があれば Resend を優先する。SMTP モードでは `RESEND_FROM_EMAIL` は無視される。

---

## Gmail SMTP（任意フォールバック）

Resend が使えないときの代替。通常運用では不要。

```bash
EMAIL_PROVIDER=smtp
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=you@gmail.com
SENDER_PASSWORD=xxxxxxxxxxxxxxxx
SUMMARY_DOGFOOD_TO=you@gmail.com
```

アプリパスワード: Google アカウントで [2段階認証](https://myaccount.google.com/security) → [アプリパスワード](https://myaccount.google.com/apppasswords)。

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

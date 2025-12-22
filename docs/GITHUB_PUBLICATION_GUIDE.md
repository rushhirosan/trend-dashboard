# GitHub公開ガイド

## ✅ GitHubに公開するメリット

1. **Reddit申請の成功率向上**
   - Redditは透明性を重視
   - 公開リポジトリがあると審査が容易
   - コードレビューが可能

2. **信頼性の向上**
   - 実装内容が確認可能
   - オープンソースとしての信頼性

3. **コミュニティからのフィードバック**
   - バグ報告や改善提案
   - コントリビューションの可能性

## ⚠️ 公開前に確認すべき点

### 1. 機密情報の確認

以下のファイル/情報が含まれていないか確認：

- [ ] `.env` ファイル（既に.gitignoreに含まれている）
- [ ] `service-account-key.json` などの認証情報ファイル
- [ ] ハードコードされたAPIキー
- [ ] データベース接続情報（本番環境の）
- [ ] メールアカウントのパスワード

### 2. .gitignoreの確認

以下のファイルが適切に除外されているか確認：

```bash
# 確認コマンド
git check-ignore -v .env
git check-ignore -v *.json
```

### 3. コミット履歴の確認

過去のコミットに機密情報が含まれていないか確認：

```bash
# 過去のコミットでAPIキーなどを検索
git log --all --full-history --source -S "API_KEY" | head -20
git log --all --full-history --source -S "password" | head -20
```

## 📝 GitHub公開の手順

### 1. 機密情報の最終確認

```bash
# 機密情報が含まれていないか確認
cd /Users/igusahiroyuki/PycharmProjects/catch_trends/trends_dashboard
grep -r "API_KEY\|SECRET\|PASSWORD" --include="*.py" --exclude-dir=.git . | grep -v "os.getenv\|os.environ" | head -20
```

### 2. README.mdの作成/更新

公開リポジトリには適切なREADMEが必要：

```markdown
# Trends Dashboard

Multi-platform trends aggregator displaying trending content from Google Trends, YouTube, Spotify, World News, Podcasts, Reddit, and more.

## Features

- Aggregates trending content from 10+ platforms
- Real-time data updates
- 24-hour caching for performance
- Responsive web dashboard

## Tech Stack

- Backend: Flask (Python 3.11)
- Database: PostgreSQL
- Deployment: Fly.io

## Setup

[セットアップ手順]

## API Keys Required

[必要なAPIキーのリスト - 実際のキーは記載しない]

## License

[ライセンスを選択]
```

### 3. GitHubリポジトリの作成

1. GitHubで新しいリポジトリを作成
2. リポジトリ名: `trends-dashboard` など
3. 公開設定: **Public**（Reddit申請のため）
4. README、.gitignore、LICENSEは既存のものを使用

### 4. 初回プッシュ

```bash
# リモートリポジトリを追加
git remote add origin https://github.com/[your-username]/trends-dashboard.git

# 現在のブランチを確認
git branch

# 初回プッシュ
git push -u origin main
```

### 5. 申請書の更新

申請書の「8. Provide a link to source code」を更新：

```
**Source Code:**
GitHub Repository: https://github.com/[your-username]/trends-dashboard

**Key Files:**
- Reddit API integration: `services/trends/reddit_trends.py`
- Main application: `app.py`
- Database caching: `database_config.py`
- API routes: `routes/trend_routes.py`

**Live Application:**
https://trends-dashboard.fly.dev
```

## 🔒 セキュリティチェックリスト

公開前に以下を確認：

- [ ] `.env` ファイルが.gitignoreに含まれている
- [ ] `*.json` ファイル（認証情報）が.gitignoreに含まれている
- [ ] ハードコードされたAPIキーがない
- [ ] データベース接続情報が環境変数から読み込まれている
- [ ] 過去のコミットに機密情報が含まれていない
- [ ] READMEに適切な説明がある
- [ ] LICENSEファイルがある（推奨）

## 💡 公開しない場合の代替案

GitHubに公開しない場合でも、以下の方法で透明性を確保：

1. **コードスニペットを申請書に直接記載**（既に改善版に含まれています）
2. **レビュー用の一時アクセスを提供**
3. **デモ環境へのアクセスを提供**
4. **技術ドキュメントを詳細に記載**

ただし、**GitHubに公開する方がReddit申請の成功率は高い**と考えられます。

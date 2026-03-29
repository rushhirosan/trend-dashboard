---
description: >-
  Run release checks (pytest, secret scan), optional git commit (manual or auto
  from diffs), push to origin main, and Fly.io deploy.
  Use when shipping, before deploy, or when the user says リリース / デプロイ /
  release / preflight / ship.
---

# Release pipeline

プロジェクトルートでシェルを実行する。**push は常に `origin main`（ローカルも `main` 必須）。**

## チェックのみ（コミット・プッシュ・デプロイしない）

```bash
./scripts/release.sh
```

1. `python3 -m pytest tests/ -q`
2. 追跡ファイルの簡易シークレット検出（GitHub PAT、秘密鍵、Google API キー風パターンなど）

## 一発リリース（おすすめ）：自動コミット文 + push main + Fly.io

変更内容から英語の1行メッセージを自動生成（例: `chore: update 3 file(s) (routes, static)`）。`tests/` のみなら `test:`、`.md` のみなら `docs:`。

```bash
./scripts/release.sh --ship
```

- チェックをすべて通した**あと** `git add -A` → コミット（変更がなければコミット省略）→ `git push origin main` → `fly deploy -a trends-dashboard`
- ローカルブランチが **`main` でないと push で失敗**する（意図的）

## 手動コミットメッセージ

```bash
./scripts/release.sh --commit "feat: your message in English" --push
./scripts/release.sh --commit "feat: your message" --push --deploy
```

## デプロイだけ（チェック通過後）

```bash
./scripts/release.sh --deploy
```

## 前提

- **Fly.io**: `fly` CLI が入り、`fly auth login` 済み。手順は [`docs/DEPLOY.md`](docs/DEPLOY.md)。
- **push**: `origin` の **main** へ送る。別ブランチで作業している場合は `main` にマージしてから `--ship` する。

## エージェント向けメモ

- 「コミットしてプッシュしてデプロイ」→ `./scripts/release.sh --ship`（メッセージ自動）。
- `memo.txt` 等にトークンが残っているとシークレットチェックで失敗する。

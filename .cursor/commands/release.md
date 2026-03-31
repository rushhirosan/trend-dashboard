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

## 一発リリース：自動コミット + push main + Fly.io

```bash
./scripts/release.sh --ship
```

- チェック後 `git add -A` → コミット → `git push origin main` → `fly deploy -a trends-dashboard`
- **自動コミット**は次を含む（`scripts/release.sh` 内の `generate_auto_commit_subject`）:
  - **件名**: 変更の種類に応じた prefix（例: `test:` / `docs:` / `chore(ui):` / `chore(api):` / `chore(ci):` / 領域混在時は `chore:`）と、**変更ファイルのベース名を最大3つ**（`+N more` で残件数）
  - **本文**: 変更パス一覧（`- path/to/file`）と、`--commit` で意図を書く旨の一行
- **背景・理由まで履歴に残したいとき**は `--ship` ではなく `--commit` を使う（下記）。

## 意図・背景を明確にしたいとき（推奨）

```bash
./scripts/release.sh --commit "fix(ui): reduce US All flicker; align with JP sync path" --push --deploy
```

`--ship` と `--commit` は同時に使えない。

## 手動コミットメッセージのみ（チェック後にその文でコミット）

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

- デプロイまで一発: `./scripts/release.sh --ship`（件名はファイル名ベース、本文にパス一覧）。
- ユーザーが「なぜ変更したか」を履歴に残したい場合は `./scripts/release.sh --commit "..." --push --deploy` を提案する。
- `memo.txt` 等にトークンが残っているとシークレットチェックで失敗する。

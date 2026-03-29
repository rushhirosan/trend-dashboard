#!/usr/bin/env bash
# リリース前チェック → 任意でコミット → 任意で push（origin main）→ 任意で Fly.io デプロイ
#
# 使い方:
#   ./scripts/release.sh
#   ./scripts/release.sh --commit "feat: something"
#   ./scripts/release.sh --commit "feat: something" --push --deploy
#   ./scripts/release.sh --deploy
#   ./scripts/release.sh --ship
#     → チェック後、変更から自動でコミットメッセージを生成し、main を push し、fly deploy

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMMIT_MSG=""
DO_DEPLOY=false
DO_PUSH=false
DO_SHIP=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      COMMIT_MSG="${2:-}"
      if [[ -z "$COMMIT_MSG" ]]; then echo "error: --commit needs a message"; exit 1; fi
      shift 2
      ;;
    --deploy)
      DO_DEPLOY=true
      shift
      ;;
    --push)
      DO_PUSH=true
      shift
      ;;
    --ship)
      DO_SHIP=true
      DO_DEPLOY=true
      DO_PUSH=true
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: $0 [options]

  (no args)     pytest, secret scan のみ
  --ship        上記のあと、変更から自動コミット → origin main へ push → fly deploy
  --commit MSG  手動メッセージでコミット（チェック通過後）
  --push        --commit または --ship と併用。origin main へ push（ローカルブランチは main 必須）
  --deploy      Fly.io のみ（チェック通過後）

例:
  $0
  $0 --commit "fix: typo" --push
  $0 --commit "chore: sync" --push --deploy
  $0 --ship
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (use --help)"
      exit 1
      ;;
  esac
done

if [[ "$DO_SHIP" == true && -n "$COMMIT_MSG" ]]; then
  echo "error: --ship と --commit は同時に使えません"
  exit 1
fi

if [[ "$DO_PUSH" == true && "$DO_SHIP" == false && -z "$COMMIT_MSG" ]]; then
  echo "error: --push は --commit または --ship と併用してください"
  exit 1
fi

generate_auto_commit_message() {
  local files=() prefix n dirs line
  while IFS= read -r line; do
    [[ -n "$line" ]] && files+=("$line")
  done < <(git diff --cached --name-only)
  n=${#files[@]}
  if [[ "$n" -eq 0 ]]; then
    echo ""
    return 1
  fi

  local all_test=true all_md=true
  for line in "${files[@]}"; do
    [[ "$line" == tests/* ]] || all_test=false
    [[ "$line" == *.md ]] || all_md=false
  done
  if [[ "$all_test" == true ]]; then
    prefix="test"
  elif [[ "$all_md" == true ]]; then
    prefix="docs"
  else
    prefix="chore"
  fi

  dirs=$(printf '%s\n' "${files[@]}" | awk -F/ 'NF>=1 { print $1 }' | sort -u | paste -sd ', ' -)
  local subject="${prefix}: update ${n} file(s) (${dirs})"
  if [[ ${#subject} -gt 72 ]]; then
    subject="${subject:0:69}..."
  fi
  echo "$subject"
}

assert_on_main_branch() {
  local cur
  cur="$(git branch --show-current)"
  if [[ "$cur" != "main" ]]; then
    echo "ERROR: push は main ブランチでのみ実行してください（現在: ${cur}）。git switch main してから再実行してください。"
    exit 1
  fi
}

echo "==> 1/2 pytest"
python3 -m pytest tests/ -q

echo "==> 2/2 秘密情報チェック（ヒューリスティック）"
FOUND=0
while IFS= read -r -d '' f; do
  case "$f" in
    *.png|*.jpg|*.jpeg|*.gif|*.webp|*.ico|*.pdf) continue ;;
  esac
  if grep -qE '(ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]+|glpat-[a-zA-Z0-9_-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35})' "$f" 2>/dev/null; then
    echo "  疑わしいパターン: $f"
    grep -nE '(ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]+|glpat-[a-zA-Z0-9_-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35})' "$f" || true
    FOUND=1
  fi
done < <(git ls-files -z)

if [[ "$FOUND" -ne 0 ]]; then
  echo "ERROR: 上記を修正するか、ローカルメモからトークンを削除してから再実行してください。"
  exit 1
fi

# --- git / push / deploy（チェック完了後のみ）---

if [[ -n "$COMMIT_MSG" ]] || [[ "$DO_SHIP" == true ]]; then
  git add -A
fi

if [[ -n "$COMMIT_MSG" ]]; then
  echo "==> git commit（手動メッセージ）"
  if git diff --cached --quiet; then
    echo "コミットする変更がありません（作業ツリーは空）"
  else
    git commit -m "$COMMIT_MSG"
  fi
elif [[ "$DO_SHIP" == true ]]; then
  echo "==> git commit（変更内容から自動生成）"
  if git diff --cached --quiet; then
    echo "変更なしのためコミットをスキップ"
  else
    AUTO_MSG="$(generate_auto_commit_message)"
    echo "  メッセージ: $AUTO_MSG"
    git commit -m "$AUTO_MSG"
  fi
fi

if [[ "$DO_PUSH" == true ]]; then
  assert_on_main_branch
  echo "==> git push origin main"
  git push origin main
fi

if [[ "$DO_DEPLOY" == true ]]; then
  echo "==> Fly.io デプロイ（fly CLI / ログイン済み想定）"
  if ! command -v fly >/dev/null 2>&1; then
    echo "ERROR: fly CLI が見つかりません。https://fly.io/docs/hands-on/install-flyctl/ を参照してください。"
    exit 1
  fi
  fly deploy -a trends-dashboard
fi

echo "OK: 完了"

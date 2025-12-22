#!/bin/bash
# コミット整理の準備スクリプト
# このスクリプトは整理計画を表示し、rebase用のファイルを生成します

echo "📋 コミット整理の準備"
echo ""

# バックアップブランチを作成
BACKUP_BRANCH="backup-before-squash-$(date +%Y%m%d-%H%M%S)"
echo "📦 バックアップブランチを作成: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✅ バックアップ完了: $BACKUP_BRANCH"
echo ""

# 最初のコミットを取得
FIRST_COMMIT=$(git log --reverse --format="%h" | head -1)
echo "📍 最初のコミット: $FIRST_COMMIT"
echo ""

echo "次のコマンドで対話的rebaseを開始します:"
echo "  git rebase -i $FIRST_COMMIT"
echo ""
echo "⚠️  注意:"
echo "  - エディタで各コミットを 'pick', 'squash', 'fixup' に変更してください"
echo "  - 'squash' または 's' で前のコミットに統合"
echo "  - 'fixup' または 'f' で前のコミットに統合（メッセージは保持）"
echo "  - 'drop' または 'd' でコミットを削除"
echo ""
read -p "rebaseを開始しますか？ (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    git rebase -i "$FIRST_COMMIT"
else
    echo "キャンセルしました。手動で実行してください:"
    echo "  git rebase -i $FIRST_COMMIT"
fi

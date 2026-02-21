#!/bin/bash
set -euo pipefail

# プロジェクトディレクトリ
PROJECT_DIR="/Users/taiyo/Documents/書類 - TaiyoのMac mini/gitfiles/claude-code-projects/Xrunning"
cd "$PROJECT_DIR"

# ログディレクトリ確保
mkdir -p "$PROJECT_DIR/logs"

# ログ設定
LOG_FILE="$PROJECT_DIR/logs/git_pull_$(date +%Y-%m-%d).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Git Pull 開始: $(date) ==="

# PATH設定（launchd環境ではPATHが限定的）
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/taiyo/.local/bin:$PATH"
export HOME="/Users/taiyo"

# ローカルに未コミットの変更がある場合はスタッシュ
if ! git diff --quiet HEAD 2>/dev/null; then
    echo "未コミットの変更を一時退避（stash）"
    git stash push -m "auto-stash before pull $(date +%Y-%m-%d_%H:%M)"
    STASHED=1
else
    STASHED=0
fi

# リモートから最新を取得
echo "git pull origin main"
git pull origin main --ff-only 2>&1 || {
    echo "WARNING: fast-forward マージ失敗。手動確認が必要です"
    # stash を戻す
    if [ "$STASHED" -eq 1 ]; then
        echo "stash を復元"
        git stash pop
    fi
    exit 1
}

# stash を戻す
if [ "$STASHED" -eq 1 ]; then
    echo "stash を復元"
    git stash pop || echo "WARNING: stash pop でコンフリクト発生。手動確認が必要です"
fi

echo "=== Git Pull 完了: $(date) ==="

#!/bin/bash
set -euo pipefail

# プロジェクトディレクトリ
PROJECT_DIR="/Users/taiyo/Documents/書類 - TaiyoのMac mini/gitfiles/claude-code-projects/Xrunning"
cd "$PROJECT_DIR"

# ログディレクトリ確保
mkdir -p "$PROJECT_DIR/logs"

# ログ設定
LOG_FILE="$PROJECT_DIR/logs/xrunning_$(date +%Y-%m-%d).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Xrunning 開始: $(date) ==="

# .envファイル読み込み
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# PATH設定（launchd環境ではPATHが限定的）
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/taiyo/.local/bin:$PATH"

# Python仮想環境アクティベート
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "ERROR: venvが見つかりません。setup.shを実行してください。"
    exit 1
fi

# メインスクリプト実行
PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/src/main.py" "$@"

EXIT_CODE=$?
echo "=== Xrunning 終了: $(date), 終了コード: $EXIT_CODE ==="
exit $EXIT_CODE

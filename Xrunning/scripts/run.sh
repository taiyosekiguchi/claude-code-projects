#!/bin/bash
set -euo pipefail

# プロジェクトディレクトリ
PROJECT_DIR="/Users/taiyo/Documents-macmini/gitfiles/claude-code-projects/Xrunning"
cd "$PROJECT_DIR"

# ログディレクトリ確保
mkdir -p "$PROJECT_DIR/logs"

# ログ設定
LOG_FILE="$PROJECT_DIR/logs/xrunning_$(date +%Y-%m-%d).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Xrunning 開始: $(date) ==="

# ネットワーク接続待ち（最大180秒）
echo "ネットワーク接続確認中..."
NETWORK_WAIT=0
while ! curl -s --max-time 5 https://dns.google > /dev/null 2>&1; do
    if [ "$NETWORK_WAIT" -ge 180 ]; then
        echo "ERROR: ネットワーク接続タイムアウト（180秒待機）。終了します。"
        exit 1
    fi
    echo "ネットワーク待機中... ${NETWORK_WAIT}秒経過"
    sleep 10
    NETWORK_WAIT=$((NETWORK_WAIT + 10))
done
echo "ネットワーク接続確認完了（${NETWORK_WAIT}秒待機）"

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

# 現在の時間で実行モードを判定
CURRENT_HOUR=$(date +%H)

if [ "$CURRENT_HOUR" -lt 10 ]; then
    # 朝（8時台）: 初回実行（収集→フィルタ→AI要約→投稿）
    echo "モード: 初回実行"
    PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/src/main.py" "$@"
else
    # 昼・夜（12時/20時台）: リトライモード
    echo "モード: リトライ"
    PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/src/main.py" --retry "$@"
fi

EXIT_CODE=$?
echo "=== Xrunning 終了: $(date), 終了コード: $EXIT_CODE ==="
exit $EXIT_CODE

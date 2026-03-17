#!/bin/bash
# Xrunning 診断スクリプト - 更新停止の原因を特定する

PROJECT_DIR="/Users/taiyo/Documents/Documents-macmini/gitfiles/claude-code-projects/Xrunning"
cd "$PROJECT_DIR"

echo "======================================"
echo "Xrunning 診断レポート"
echo "実行日時: $(date)"
echo "======================================"
echo ""

# 1. launchd ジョブの状態確認
echo "--- [1] launchd ジョブ状態 ---"
if launchctl list | grep -q "xrunning"; then
    echo "OK: launchd に登録済み"
    launchctl list | grep xrunning
else
    echo "ERROR: launchd に登録されていません"
    echo "  → 次のコマンドで登録してください:"
    echo "    ln -sf \"$PROJECT_DIR/launchd/com.taiyo.xrunning.plist\" ~/Library/LaunchAgents/"
    echo "    launchctl load ~/Library/LaunchAgents/com.taiyo.xrunning.plist"
fi
echo ""

# 2. venv の確認
echo "--- [2] Python venv ---"
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    echo "OK: venv が存在します"
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "ERROR: venv が見つかりません。setup.sh を実行してください"
    exit 1
fi
echo ""

# 3. .env ファイルの確認
echo "--- [3] .env ファイル ---"
if [ -f "$PROJECT_DIR/.env" ]; then
    echo "OK: .env が存在します"
    # キーが設定されているか確認（値は表示しない）
    source "$PROJECT_DIR/.env"
    for key in X_API_KEY X_API_SECRET X_ACCESS_TOKEN X_ACCESS_TOKEN_SECRET; do
        if [ -n "${!key}" ]; then
            echo "  $key: 設定済み"
        else
            echo "  $key: 未設定 ← ERROR"
        fi
    done
else
    echo "ERROR: .env ファイルが見つかりません"
fi
echo ""

# 4. Claude CLI の確認
echo "--- [4] Claude CLI ---"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/taiyo/.local/bin:$PATH"
if command -v claude &> /dev/null; then
    CLAUDE_VER=$(claude --version 2>&1 | head -1)
    echo "OK: claude コマンド発見 ($CLAUDE_VER)"
    # ログイン状態確認
    echo "ログイン状態確認中..."
    LOGIN_RESULT=$(echo "テスト" | claude -p --model sonnet 2>&1 | head -3)
    if echo "$LOGIN_RESULT" | grep -q "Not logged in"; then
        echo "ERROR: Claude CLI がログインしていません"
        echo "  → Mac mini のターミナルで 'claude' を実行してログインしてください"
    elif echo "$LOGIN_RESULT" | grep -q "nested\|CLAUDECODE"; then
        echo "WARNING: Claude Code セッション内で実行されています（launchd実行時は問題なし）"
    else
        echo "OK: Claude CLI は正常に動作しています"
        echo "  出力（最初の100文字）: ${LOGIN_RESULT:0:100}"
    fi
else
    echo "ERROR: claude コマンドが見つかりません"
fi
echo ""

# 5. 最新ログの確認
echo "--- [5] 最新ログ（直近20行）---"
LOG_TODAY="$PROJECT_DIR/logs/xrunning_$(date +%Y-%m-%d).log"
LOG_YESTERDAY="$PROJECT_DIR/logs/xrunning_$(date -v-1d +%Y-%m-%d).log"
LAUNCHD_ERR="$PROJECT_DIR/logs/launchd_stderr.log"

if [ -f "$LOG_TODAY" ]; then
    echo "本日のログ ($LOG_TODAY):"
    tail -20 "$LOG_TODAY"
elif [ -f "$LOG_YESTERDAY" ]; then
    echo "昨日のログ ($LOG_YESTERDAY):"
    tail -20 "$LOG_YESTERDAY"
else
    echo "WARNING: ログファイルが見つかりません（一度も実行されていない可能性）"
fi

if [ -f "$LAUNCHD_ERR" ] && [ -s "$LAUNCHD_ERR" ]; then
    echo ""
    echo "launchd stderr ログ（直近10行）:"
    tail -10 "$LAUNCHD_ERR"
fi
echo ""

# 6. post_status.json の確認
echo "--- [6] 投稿状態ファイル ---"
STATUS_FILE="$PROJECT_DIR/data/cache/post_status.json"
if [ -f "$STATUS_FILE" ]; then
    echo "post_status.json の内容:"
    cat "$STATUS_FILE"
else
    echo "ファイルなし（正常）"
fi
echo ""

echo "======================================"
echo "診断完了"
echo "======================================"

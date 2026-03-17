#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/taiyo/Documents/Documents-macmini/gitfiles/claude-code-projects/Xrunning"
cd "$PROJECT_DIR"

echo "=== Xrunning セットアップ ==="

# Python仮想環境の作成
if [ ! -d "venv" ]; then
    echo "Python仮想環境を作成中..."
    python3 -m venv venv
fi

# 依存パッケージのインストール
echo "依存パッケージをインストール中..."
source venv/bin/activate
pip install -r requirements.txt

# データディレクトリの作成
mkdir -p data/raw data/filtered data/posts data/cache logs

# .envファイルの確認
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .envファイルが見つかりません。"
    echo ".env.exampleをコピーしてAPIキーを設定してください:"
    echo "  cp .env.example .env"
    echo "  nano .env"
fi

# launchdの登録
echo ""
echo "launchdの登録 (任意):"
echo "  ln -sf \"$PROJECT_DIR/launchd/com.taiyo.xrunning.plist\" ~/Library/LaunchAgents/"
echo "  launchctl load ~/Library/LaunchAgents/com.taiyo.xrunning.plist"

# Claude CLIの確認
if command -v claude &> /dev/null; then
    echo ""
    echo "Claude CLI: OK ($(which claude))"
else
    echo ""
    echo "WARNING: claude コマンドが見つかりません。"
    echo "Claude Code CLIをインストールしてください。"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "1. .envファイルにX APIキーを設定"
echo "2. テスト実行: bash scripts/run.sh --dry-run"
echo "3. launchdを登録して自動化"

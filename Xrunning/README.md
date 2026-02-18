# Xrunning - AIニュース自動収集・X投稿システム

毎朝8時に自動起動し、AI関連ニュースを収集・要約してXにスレッド形式で投稿するシステム。

## 機能

- **情報収集**: RSS (TechCrunch AI, ITmedia AI+, GIGAZINE等)、Hacker News、GitHub Trending
- **フィルタリング**: AI関連キーワードで抽出、重複排除、重要度スコアリング
- **AI要約**: Claude Code CLI (`claude -p`) でスレッド形式の日本語記事を生成
- **自動投稿**: tweepy v2 でXにスレッド形式で投稿
- **自動化**: macOS launchd で毎朝8:00に自動実行

## セットアップ

```bash
# 初期セットアップ
bash scripts/setup.sh

# .envにAPIキーを設定
cp .env.example .env
nano .env

# テスト実行（投稿なし）
bash scripts/run.sh --dry-run
```

## X APIキーの取得

1. [X Developer Portal](https://developer.x.com/en/portal/dashboard) にアクセス
2. Free プランでアプリを作成
3. Consumer Keys (API Key & Secret) を取得
4. Authentication Tokens (Access Token & Secret) を生成
5. `.env` に設定

## launchd（自動実行）の設定

```bash
# plistをLaunchAgentsにリンク
ln -sf "$(pwd)/launchd/com.taiyo.xrunning.plist" ~/Library/LaunchAgents/

# 登録
launchctl load ~/Library/LaunchAgents/com.taiyo.xrunning.plist

# 手動テスト
launchctl start com.taiyo.xrunning

# 確認
launchctl list | grep xrunning

# 停止
launchctl unload ~/Library/LaunchAgents/com.taiyo.xrunning.plist
```

## 技術スタック

- Python 3.13+
- feedparser (RSS解析)
- tweepy (X API v2)
- aiohttp (非同期HTTP)
- BeautifulSoup4 (HTMLパース)
- Claude Code CLI (AI要約)
- macOS launchd (スケジュール実行)

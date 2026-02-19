"""全体設定: ソースURL、フィルタキーワード、定数"""

from pathlib import Path

# プロジェクトルート
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
LOG_DIR = PROJECT_DIR / "logs"

# RSSフィード {ソース名: URL}
RSS_FEEDS = {
    # 海外
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    # 日本語
    "ITmedia AI+": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "GIGAZINE": "https://gigazine.net/news/rss_2.0/",
}

# Hacker News (hnrss.org経由)
HACKERNEWS_RSS_URLS = [
    "https://hnrss.org/newest?q=AI&count=40",
    "https://hnrss.org/newest?q=Claude+AI&count=20",
    "https://hnrss.org/newest?q=LLM&count=20",
]

# GitHub Trending
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# フィルタキーワード（タイトル・要約にこれらが含まれる記事を抽出）
AI_KEYWORDS = [
    # 英語
    "artificial intelligence", "machine learning", "deep learning",
    "LLM", "GPT", "Claude", "Anthropic", "OpenAI", "Gemini", "Mistral",
    "transformer", "neural network", "AGI", "AI agent",
    "Claude Code", "Copilot", "Cursor", "AI coding",
    "diffusion model", "foundation model", "fine-tuning",
    # 日本語
    "AI", "生成AI", "大規模言語モデル", "機械学習", "深層学習",
    "人工知能", "チャットボット", "AIエージェント",
]

# Claude/Anthropic関連（ボーナススコア付与）
CLAUDE_KEYWORDS = [
    "Claude", "Anthropic", "Claude Code", "claude-sonnet", "claude-opus",
    "claude-haiku", "MCP", "Model Context Protocol",
]

# ソース信頼度スコア倍率
SOURCE_TRUST_SCORES = {
    "TechCrunch AI": 1.5,
    "MIT Tech Review": 1.5,
    "The Verge AI": 1.3,
    "Ars Technica": 1.3,
    "ITmedia AI+": 1.3,
    "GIGAZINE": 1.0,
    "Hacker News": 1.2,
    "GitHub Trending": 1.0,
}

# 処理設定
MAX_ARTICLES_FOR_AI = 10  # Claude CLIに渡す最大記事数
THREAD_MAX_TWEETS = 5  # スレッド最大ツイート数（X API制限対策で5に制限）
TWEET_MAX_LENGTH = 270  # 280 - ハッシュタグ等のバッファ
URL_LENGTH = 23  # X のt.co短縮URL長

# 重複排除
DEDUP_TITLE_THRESHOLD = 0.8  # タイトル類似度の閾値
CACHE_DAYS = 7  # 投稿済みURLキャッシュ保持日数

# Claude CLI
CLAUDE_TIMEOUT = 120  # 秒
CLAUDE_MAX_RETRIES = 3
CLAUDE_RETRY_INTERVAL = 30  # 秒

# X API投稿
X_POST_MAX_RETRIES = 4

# データクリーンアップ
DATA_RETENTION_DAYS = 30

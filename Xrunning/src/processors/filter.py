"""キーワードフィルタリング"""

import logging

from config.settings import AI_KEYWORDS
from src.models.article import Article

logger = logging.getLogger("xrunning.filter")

# 小文字化したキーワードセット
_AI_KEYWORDS_LOWER = [kw.lower() for kw in AI_KEYWORDS]


def filter_by_keywords(articles: list[Article]) -> list[Article]:
    """AI関連キーワードにマッチする記事のみ抽出する"""
    filtered = []
    for article in articles:
        text = f"{article.title} {article.summary}".lower()
        matched = [kw for kw in _AI_KEYWORDS_LOWER if kw in text]
        if matched:
            article.keywords = matched
            filtered.append(article)

    logger.debug(f"キーワードフィルタ: {len(articles)} -> {len(filtered)}件")
    return filtered

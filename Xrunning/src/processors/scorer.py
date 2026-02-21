"""重要度スコアリング"""

import logging

from config.settings import CLAUDE_KEYWORDS, SOURCE_TRUST_SCORES
from src.models.article import Article

logger = logging.getLogger("xrunning.scorer")

_CLAUDE_KEYWORDS_LOWER = [kw.lower() for kw in CLAUDE_KEYWORDS]


def score_articles(
    articles: list[Article],
    topic_boosts: dict[str, float] | None = None,
) -> list[Article]:
    """記事にスコアを付与し、降順ソートで返す

    Args:
        articles: スコアリング対象の記事リスト
        topic_boosts: エンゲージメント分析に基づくトピック別ブースト値
                      例: {"claude": 1.5, "openai": 1.2, "hardware": 0.7}
    """
    for article in articles:
        score = 0.0
        text = f"{article.title} {article.summary}".lower()

        # キーワードマッチ数ベース
        score += len(article.keywords) * 1.0

        # ソース信頼度
        trust = SOURCE_TRUST_SCORES.get(article.source, 1.0)
        score *= trust

        # Claude/Anthropic関連ボーナス
        if any(kw in text for kw in _CLAUDE_KEYWORDS_LOWER):
            score *= 2.0

        # 日本語ソースボーナス（日本のオーディエンス向け）
        if article.language == "ja":
            score *= 1.3

        # エンゲージメント分析に基づくトピックブースト
        if topic_boosts:
            max_boost = 1.0
            for keyword in article.keywords:
                boost = topic_boosts.get(keyword.lower(), 1.0)
                max_boost = max(max_boost, boost)
            if max_boost != 1.0:
                score *= max_boost
                logger.debug(
                    f"トピックブースト適用: {article.title[:30]}... x{max_boost}"
                )

        article.score = round(score, 2)

    articles.sort(key=lambda a: a.score, reverse=True)

    if articles:
        logger.debug(
            f"スコアリング完了: 最高={articles[0].score}, "
            f"最低={articles[-1].score}, 中央={articles[len(articles)//2].score}"
        )

    return articles

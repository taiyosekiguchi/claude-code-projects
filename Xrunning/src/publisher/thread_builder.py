"""スレッド構築・文字数バリデーション"""

import logging

from config.settings import THREAD_MAX_TWEETS, TWEET_MAX_LENGTH

logger = logging.getLogger("xrunning.thread_builder")


def validate_thread(tweets: list[str]) -> list[str]:
    """スレッドの文字数を検証し、必要に応じて調整する"""
    # ツイート数制限
    if len(tweets) > THREAD_MAX_TWEETS:
        logger.warning(
            f"ツイート数が上限超過: {len(tweets)} > {THREAD_MAX_TWEETS}。切り詰め"
        )
        tweets = tweets[:THREAD_MAX_TWEETS]

    validated = []
    for i, tweet in enumerate(tweets):
        if len(tweet) > 280:
            logger.warning(f"ツイート{i+1}が280文字超過 ({len(tweet)}文字)。分割処理")
            split = _split_tweet(tweet)
            validated.extend(split)
        else:
            validated.append(tweet)

    # 再度ツイート数制限チェック
    if len(validated) > THREAD_MAX_TWEETS:
        validated = validated[:THREAD_MAX_TWEETS]

    return validated


def _split_tweet(tweet: str) -> list[str]:
    """280文字超過のツイートを適切な位置で分割する"""
    if len(tweet) <= 280:
        return [tweet]

    parts = []
    remaining = tweet

    while remaining:
        if len(remaining) <= 280:
            parts.append(remaining)
            break

        # 句点（。）、改行、読点（、）の順で分割ポイントを探す
        split_pos = _find_split_point(remaining, TWEET_MAX_LENGTH)
        parts.append(remaining[:split_pos].rstrip())
        remaining = remaining[split_pos:].lstrip()

    return parts


def _find_split_point(text: str, max_len: int) -> int:
    """分割に適した位置を見つける"""
    search_range = text[:max_len]

    # 改行で分割
    pos = search_range.rfind("\n")
    if pos > max_len // 2:
        return pos + 1

    # 句点で分割
    pos = search_range.rfind("。")
    if pos > max_len // 2:
        return pos + 1

    # 読点で分割
    pos = search_range.rfind("、")
    if pos > max_len // 2:
        return pos + 1

    # ピリオドで分割
    pos = search_range.rfind(". ")
    if pos > max_len // 2:
        return pos + 2

    # どれも見つからない場合は最大長で切る
    return max_len

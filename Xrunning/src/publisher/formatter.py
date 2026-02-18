"""ツイート整形（ハッシュタグ等の付加）"""

import logging

logger = logging.getLogger("xrunning.formatter")


def add_thread_numbers(tweets: list[str]) -> list[str]:
    """各ツイートにスレッド番号を付与する（先頭に「n/N」）"""
    total = len(tweets)
    # 先頭と末尾は番号なし（導入・まとめ）
    if total <= 2:
        return tweets

    numbered = [tweets[0]]
    for i, tweet in enumerate(tweets[1:-1], 1):
        numbered.append(f"{i}/{total-2} {tweet}")
    numbered.append(tweets[-1])

    return numbered

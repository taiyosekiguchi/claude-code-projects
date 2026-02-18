"""tweepy v2 によるX投稿クライアント"""

import logging
import os
import time

import tweepy

from config.settings import X_POST_MAX_RETRIES, X_POST_RETRY_INTERVAL

logger = logging.getLogger("xrunning.twitter")


class TwitterPublisher:
    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )

    def post_thread(self, tweets: list[str]) -> list[str]:
        """
        スレッド形式で投稿する。
        1ツイート目を投稿し、以降はin_reply_to_tweet_idで連鎖。
        """
        tweet_ids = []
        reply_to = None

        for i, tweet_text in enumerate(tweets):
            tweet_id = self._post_single(tweet_text, reply_to, i + 1, len(tweets))
            if tweet_id is None:
                logger.error(f"ツイート{i+1}/{len(tweets)}の投稿に失敗。スレッドを中断")
                break
            tweet_ids.append(tweet_id)
            reply_to = tweet_id

            # レートリミット対策の待機（X APIは短時間連続投稿に厳しい）
            if i < len(tweets) - 1:
                time.sleep(5)

        return tweet_ids

    def _post_single(
        self, text: str, reply_to: str | None, num: int, total: int
    ) -> str | None:
        """単一ツイートを投稿する（リトライあり）"""
        for attempt in range(1, X_POST_MAX_RETRIES + 1):
            try:
                response = self.client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=reply_to,
                )
                tweet_id = response.data["id"]
                logger.info(f"ツイート投稿成功 [{num}/{total}]: id={tweet_id}")
                return tweet_id

            except tweepy.TooManyRequests as e:
                logger.error(f"レートリミット超過: {e}")
                return None

            except tweepy.TweepyException as e:
                logger.error(f"投稿失敗 (試行{attempt}/{X_POST_MAX_RETRIES}): {e}")
                if attempt < X_POST_MAX_RETRIES:
                    time.sleep(X_POST_RETRY_INTERVAL)

        return None

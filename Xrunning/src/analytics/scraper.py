"""Playwright ベースのツイートメトリクス収集"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass

logger = logging.getLogger("xrunning.analytics.scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


@dataclass
class TweetMetrics:
    views: int = 0
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    bookmarks: int = 0

    def to_dict(self) -> dict:
        return {
            "views": self.views,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "quotes": self.quotes,
            "bookmarks": self.bookmarks,
        }


def _parse_count(text: str) -> int:
    """エンゲージメント数値をパースする（例: "1.2K" -> 1200, "3M" -> 3000000）"""
    if not text:
        return 0
    text = text.strip().replace(",", "")

    match = re.match(r"^([\d.]+)\s*([KMB]?)$", text, re.IGNORECASE)
    if not match:
        # 数字のみ抽出を試行
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    num = float(match.group(1))
    suffix = match.group(2).upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(num * multiplier.get(suffix, 1))


class TweetMetricsScraper:
    """公開ツイートページからメトリクスをスクレイピング"""

    def __init__(self, delay_between_tweets: int = 15):
        self.delay = delay_between_tweets
        self._browser = None
        self._context = None

    async def __aenter__(self):
        await self._start_browser()
        return self

    async def __aexit__(self, *args):
        await self._close_browser()

    async def _start_browser(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright がインストールされていません。pip install playwright && playwright install chromium を実行してください")
            raise

        self._playwright = await async_playwright().start()
        ua = random.choice(USER_AGENTS)
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 720},
            locale="ja-JP",
        )
        logger.debug(f"ブラウザ起動: UA={ua[:50]}...")

    async def _close_browser(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.debug("ブラウザ終了")

    async def scrape_tweet(self, tweet_url: str) -> TweetMetrics | None:
        """単一ツイートのメトリクスを取得"""
        if not self._context:
            logger.error("ブラウザが起動されていません")
            return None

        page = await self._context.new_page()
        metrics = TweetMetrics()

        try:
            logger.debug(f"スクレイピング: {tweet_url}")
            await page.goto(tweet_url, wait_until="domcontentloaded", timeout=30000)

            # ツイート本文が表示されるまで待機（最大15秒）
            try:
                await page.wait_for_selector("[data-testid='tweetText']", timeout=15000)
            except Exception:
                logger.debug("tweetText セレクタのタイムアウト。ページ読み込みを続行")

            # 追加の描画待ち
            await page.wait_for_timeout(3000)

            # === メトリクス抽出 ===

            # 方法1: aria-label からの抽出（最も安定）
            metrics = await self._extract_from_aria_labels(page, metrics)

            # 方法2: data-testid ベースの抽出（フォールバック）
            if metrics.views == 0 and metrics.likes == 0:
                metrics = await self._extract_from_testid(page, metrics)

            # 方法3: テキストベースのフォールバック
            if metrics.views == 0 and metrics.likes == 0:
                metrics = await self._extract_from_text(page, metrics)

            logger.info(
                f"メトリクス取得: views={metrics.views}, likes={metrics.likes}, "
                f"RT={metrics.retweets}, replies={metrics.replies}"
            )
            return metrics

        except Exception as e:
            logger.error(f"スクレイピング失敗 ({tweet_url}): {e}")
            return None
        finally:
            await page.close()

    def _extract_number_from_aria(self, aria: str) -> int:
        """aria-label から先頭の数値を抽出（例: '1 件の返信。返信する' → 1）"""
        m = re.match(r"([\d,.]+(?:\.\d+)?)\s*([KMBkmb])?", aria.strip())
        if m:
            return _parse_count(m.group(0))
        return 0

    async def _extract_from_aria_labels(self, page, metrics: TweetMetrics) -> TweetMetrics:
        """aria-label 属性からメトリクスを抽出"""
        try:
            # X の公開ツイートページでは aria-label に「N 件の〇〇」形式で数値が含まれる
            elements = await page.query_selector_all("[role='group'] [role='button']")
            for el in elements:
                aria = await el.get_attribute("aria-label")
                if not aria:
                    continue

                count = self._extract_number_from_aria(aria)

                # 各メトリクスのパターンマッチ
                if "いいね" in aria or "like" in aria.lower():
                    metrics.likes = count
                elif "リポスト" in aria or "repost" in aria.lower():
                    metrics.retweets = count
                elif "返信" in aria or "repl" in aria.lower():
                    metrics.replies = count
                elif "ブックマーク" in aria or "bookmark" in aria.lower():
                    metrics.bookmarks = count
                elif "表示" in aria or "view" in aria.lower():
                    metrics.views = count

            # views は analytics リンクや表示回数要素から取得
            if metrics.views == 0:
                view_link = await page.query_selector("a[href*='/analytics']")
                if view_link:
                    aria = await view_link.get_attribute("aria-label")
                    if aria:
                        metrics.views = self._extract_number_from_aria(aria)
                    else:
                        text = await view_link.inner_text()
                        metrics.views = _parse_count(text.strip())

        except Exception as e:
            logger.debug(f"aria-label抽出エラー: {e}")

        return metrics

    async def _extract_from_testid(self, page, metrics: TweetMetrics) -> TweetMetrics:
        """data-testid ベースでメトリクスを抽出"""
        try:
            selectors = {
                "likes": "[data-testid='like']",
                "retweets": "[data-testid='retweet']",
                "replies": "[data-testid='reply']",
                "bookmarks": "[data-testid='bookmark']",
            }

            for metric_name, selector in selectors.items():
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    count = _parse_count(text)
                    if count > 0:
                        setattr(metrics, metric_name, count)

        except Exception as e:
            logger.debug(f"data-testid抽出エラー: {e}")

        return metrics

    async def _extract_from_text(self, page, metrics: TweetMetrics) -> TweetMetrics:
        """ページテキスト全体から数値を抽出するフォールバック"""
        try:
            content = await page.content()

            # views のパターン (よくある表示形式)
            view_patterns = [
                r'"viewCount":\s*(\d+)',
                r'"views":\s*"?(\d+)"?',
                r'(\d[\d,.]*)\s*(?:views|表示)',
            ]
            for pattern in view_patterns:
                m = re.search(pattern, content, re.IGNORECASE)
                if m and metrics.views == 0:
                    metrics.views = _parse_count(m.group(1))
                    break

        except Exception as e:
            logger.debug(f"テキスト抽出エラー: {e}")

        return metrics

    async def scrape_thread(
        self, tweet_ids: list[str], username: str
    ) -> list[tuple[str, TweetMetrics | None]]:
        """スレッド内の全ツイートをスクレイピング"""
        results = []

        for i, tweet_id in enumerate(tweet_ids):
            tweet_url = f"https://x.com/{username}/status/{tweet_id}"
            metrics = await self.scrape_tweet(tweet_url)
            results.append((tweet_id, metrics))

            # 最後のツイート以外は待機
            if i < len(tweet_ids) - 1:
                delay = self.delay + random.randint(0, 5)
                logger.debug(f"{delay}秒待機...")
                await asyncio.sleep(delay)

        return results

    async def scrape_follower_count(self, username: str) -> tuple[int, int] | None:
        """プロフィールページからフォロワー数とフォロー数を取得"""
        if not self._context:
            return None

        page = await self._context.new_page()
        try:
            profile_url = f"https://x.com/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)

            # プロフィール情報が表示されるまで待機
            try:
                await page.wait_for_selector(f"a[href='/{username}/verified_followers']", timeout=15000)
            except Exception:
                logger.debug("フォロワーリンクのタイムアウト。ページ読み込みを続行")

            await page.wait_for_timeout(3000)

            followers = 0
            following = 0

            # フォロワーリンクからの抽出
            follower_link = await page.query_selector(f"a[href='/{username}/verified_followers']")
            if follower_link:
                text = await follower_link.inner_text()
                followers = _parse_count(re.sub(r"[^\d.KMBkmb,]", "", text))

            following_link = await page.query_selector(f"a[href='/{username}/following']")
            if following_link:
                text = await following_link.inner_text()
                following = _parse_count(re.sub(r"[^\d.KMBkmb,]", "", text))

            logger.info(f"フォロワー数: {followers}, フォロー数: {following}")
            return (followers, following)

        except Exception as e:
            logger.error(f"プロフィールスクレイピング失敗: {e}")
            return None
        finally:
            await page.close()

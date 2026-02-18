"""Hacker News 収集モジュール（hnrss.org RSS経由）"""

import logging
from datetime import datetime, timedelta, timezone
from time import mktime

import aiohttp
import feedparser

from config.settings import HACKERNEWS_RSS_URLS
from src.collectors.base import BaseCollector
from src.models.article import Article

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("xrunning.hackernews")


class HackerNewsCollector(BaseCollector):
    async def collect(self) -> list[Article]:
        articles = []
        seen_urls = set()
        async with aiohttp.ClientSession() as session:
            for url in HACKERNEWS_RSS_URLS:
                try:
                    fetched = await self._fetch_feed(session, url)
                    for article in fetched:
                        if article.url not in seen_urls:
                            seen_urls.add(article.url)
                            articles.append(article)
                except Exception as e:
                    logger.error(f"HN RSS取得失敗 [{url}]: {e}")
        return articles

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, url: str
    ) -> list[Article]:
        headers = {
            "User-Agent": "Xrunning/1.0 (AI News Bot)"
        }
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()

        feed = feedparser.parse(text)
        articles = []
        for entry in feed.entries:
            published = self._parse_date(entry)
            if published is None:
                continue

            # hnrss.orgではlinkが元記事URL、commentsがHN議論ページ
            article_url = entry.get("link", "").strip()
            comments_url = entry.get("comments", "")

            summary = ""
            if hasattr(entry, "summary"):
                import re
                summary = re.sub(r"<[^>]+>", "", entry.summary).strip()[:500]

            articles.append(
                Article(
                    title=entry.get("title", "").strip(),
                    url=article_url,
                    source="Hacker News",
                    published=published,
                    summary=summary,
                    language="en",
                )
            )

        logger.debug(f"[HN] {len(articles)}件パース完了 ({url})")
        return articles

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                    return dt.astimezone(JST)
                except (ValueError, OverflowError):
                    pass
        return None

"""RSS フィード収集モジュール"""

import logging
from datetime import datetime, timedelta, timezone
from time import mktime

import aiohttp
import feedparser

from config.settings import RSS_FEEDS
from src.collectors.base import BaseCollector
from src.models.article import Article

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("xrunning.rss")

# 日本語ソース判定用
JA_SOURCES = {"ITmedia AI+", "GIGAZINE"}


class RSSCollector(BaseCollector):
    async def collect(self) -> list[Article]:
        articles = []
        async with aiohttp.ClientSession() as session:
            for source_name, url in RSS_FEEDS.items():
                try:
                    fetched = await self._fetch_feed(session, source_name, url)
                    articles.extend(fetched)
                except Exception as e:
                    logger.error(f"RSS取得失敗 [{source_name}]: {e}")
        return articles

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, source_name: str, url: str
    ) -> list[Article]:
        headers = {
            "User-Agent": "Xrunning/1.0 (AI News Bot; +https://github.com/taiyosekiguchi)"
        }
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()

        feed = feedparser.parse(text)
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS解析警告 [{source_name}]: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries:
            published = self._parse_date(entry)
            if published is None:
                continue

            summary = ""
            if hasattr(entry, "summary"):
                summary = self._strip_html(entry.summary)[:500]
            elif hasattr(entry, "description"):
                summary = self._strip_html(entry.description)[:500]

            lang = "ja" if source_name in JA_SOURCES else "en"

            articles.append(
                Article(
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", "").strip(),
                    source=source_name,
                    published=published,
                    summary=summary,
                    language=lang,
                )
            )

        logger.debug(f"[{source_name}] {len(articles)}件パース完了")
        return articles

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        """RSSエントリから日時を解析する"""
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                    return dt.astimezone(JST)
                except (ValueError, OverflowError):
                    pass

        for attr in ("published", "updated"):
            raw = getattr(entry, attr, None)
            if raw:
                try:
                    return datetime.fromisoformat(raw).astimezone(JST)
                except ValueError:
                    pass

        return None

    @staticmethod
    def _strip_html(text: str) -> str:
        """HTMLタグを簡易的に除去する"""
        import re
        return re.sub(r"<[^>]+>", "", text).strip()

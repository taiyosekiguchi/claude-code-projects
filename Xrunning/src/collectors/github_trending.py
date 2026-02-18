"""GitHub Trending 収集モジュール"""

import logging
import re
from datetime import datetime, timedelta, timezone

import aiohttp
from bs4 import BeautifulSoup

from config.settings import GITHUB_TRENDING_URL, AI_KEYWORDS
from src.collectors.base import BaseCollector
from src.models.article import Article

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("xrunning.github")

# GitHub TrendingでAI関連と判断するキーワード（小文字）
GH_AI_KEYWORDS = {kw.lower() for kw in AI_KEYWORDS} | {
    "llm", "gpt", "transformer", "diffusion", "rag",
    "langchain", "llamaindex", "ollama", "vllm",
    "pytorch", "tensorflow", "huggingface",
}


class GitHubTrendingCollector(BaseCollector):
    async def collect(self) -> list[Article]:
        try:
            return await self._fetch_trending()
        except Exception as e:
            logger.error(f"GitHub Trending取得失敗: {e}")
            return []

    async def _fetch_trending(self) -> list[Article]:
        headers = {
            "User-Agent": "Xrunning/1.0 (AI News Bot)",
            "Accept": "text/html",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GITHUB_TRENDING_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("article.Box-row")

        articles = []
        now = datetime.now(JST)

        for row in rows:
            try:
                article = self._parse_row(row, now)
                if article and self._is_ai_related(article):
                    articles.append(article)
            except Exception as e:
                logger.debug(f"GitHub行パース失敗: {e}")

        logger.debug(f"[GitHub] AI関連{len(articles)}件抽出 (全{len(rows)}件中)")
        return articles

    def _parse_row(self, row, now: datetime) -> Article | None:
        # リポジトリ名
        h2 = row.select_one("h2 a")
        if not h2:
            return None
        repo_path = h2.get("href", "").strip("/")
        if not repo_path:
            return None

        # 説明文
        p = row.select_one("p")
        description = p.get_text(strip=True) if p else ""

        # スター数
        stars_text = ""
        star_links = row.select("a.Link--muted")
        for link in star_links:
            if "/stargazers" in link.get("href", ""):
                stars_text = link.get_text(strip=True).replace(",", "")
                break

        url = f"https://github.com/{repo_path}"

        return Article(
            title=repo_path,
            url=url,
            source="GitHub Trending",
            published=now,
            summary=description,
            language="en",
        )

    @staticmethod
    def _is_ai_related(article: Article) -> bool:
        text = f"{article.title} {article.summary}".lower()
        return any(kw in text for kw in GH_AI_KEYWORDS)

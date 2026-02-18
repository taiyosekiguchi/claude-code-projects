"""コレクター基底クラス"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from src.models.article import Article

JST = timezone(timedelta(hours=9))


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> list[Article]:
        """記事を収集して返す"""
        ...

    def filter_by_date(
        self, articles: list[Article], since: datetime
    ) -> list[Article]:
        """指定日時以降の記事のみ抽出"""
        return [a for a in articles if a.published >= since]

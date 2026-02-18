"""記事データモデル"""

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: datetime
    summary: str = ""
    score: float = 0.0
    language: str = "en"
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        data = data.copy()
        if isinstance(data.get("published"), str):
            data["published"] = datetime.fromisoformat(data["published"])
        return cls(**data)

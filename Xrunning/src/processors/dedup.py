"""重複排除"""

import json
import logging
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from config.settings import CACHE_DAYS, DATA_DIR, DEDUP_TITLE_THRESHOLD
from src.models.article import Article

logger = logging.getLogger("xrunning.dedup")

CACHE_FILE = DATA_DIR / "cache" / "posted_urls.json"


def _normalize_url(url: str) -> str:
    """URLを正規化する（クエリパラメータ除去、www除去等）"""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse(("", host, path, "", "", ""))


def _load_posted_cache() -> set[str]:
    """過去の投稿済みURLキャッシュを読み込む"""
    if not CACHE_FILE.exists():
        return set()
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cutoff = (date.today() - timedelta(days=CACHE_DAYS)).isoformat()
        return {
            entry["url"]
            for entry in data
            if entry.get("date", "") >= cutoff
        }
    except Exception as e:
        logger.warning(f"キャッシュ読み込み失敗: {e}")
        return set()


def save_posted_urls(urls: list[str]) -> None:
    """投稿済みURLをキャッシュに追加する"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if CACHE_FILE.exists():
        try:
            existing = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    today = date.today().isoformat()
    for url in urls:
        existing.append({"url": _normalize_url(url), "date": today})

    # 古いエントリを削除
    cutoff = (date.today() - timedelta(days=CACHE_DAYS)).isoformat()
    existing = [e for e in existing if e.get("date", "") >= cutoff]

    CACHE_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def deduplicate(articles: list[Article]) -> list[Article]:
    """URL・タイトル類似度による重複排除"""
    posted_cache = _load_posted_cache()
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    result: list[Article] = []

    for article in articles:
        norm_url = _normalize_url(article.url)

        # 過去の投稿済みURLチェック
        if norm_url in posted_cache:
            continue

        # URL重複チェック
        if norm_url in seen_urls:
            continue

        # タイトル類似度チェック
        is_dup = False
        for seen_title in seen_titles:
            ratio = SequenceMatcher(None, article.title, seen_title).ratio()
            if ratio >= DEDUP_TITLE_THRESHOLD:
                is_dup = True
                break

        if is_dup:
            continue

        seen_urls.add(norm_url)
        seen_titles.append(article.title)
        result.append(article)

    logger.debug(f"重複排除: {len(articles)} -> {len(result)}件")
    return result

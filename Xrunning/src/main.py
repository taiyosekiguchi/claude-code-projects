"""メインオーケストレーター: 収集 → フィルタ → AI要約 → X投稿"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import DATA_DIR, LOG_DIR, MAX_ARTICLES_FOR_AI
from src.ai.summarizer import generate_thread, build_fallback_thread
from src.collectors.rss_collector import RSSCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.github_trending import GitHubTrendingCollector
from src.processors.filter import filter_by_keywords
from src.processors.dedup import deduplicate
from src.processors.scorer import score_articles
from src.publisher.twitter_client import TwitterPublisher
from src.publisher.thread_builder import validate_thread

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("xrunning")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        LOG_DIR / f"xrunning_{date.today()}.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(fmt)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


async def collect_all() -> list:
    """全コレクターを並行実行して記事を収集する"""
    collectors = [
        RSSCollector(),
        HackerNewsCollector(),
        GitHubTrendingCollector(),
    ]

    results = await asyncio.gather(
        *[c.collect() for c in collectors],
        return_exceptions=True,
    )

    all_articles = []
    for collector, result in zip(collectors, results):
        name = collector.__class__.__name__
        if isinstance(result, Exception):
            logger.error(f"{name} 収集失敗: {result}")
        else:
            logger.info(f"{name}: {len(result)}件取得")
            all_articles.extend(result)

    return all_articles


def save_json(data: list[dict], subdir: str, filename: str) -> Path:
    """中間データをJSONファイルに保存する"""
    dir_path = DATA_DIR / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    filepath = dir_path / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return filepath


def save_post_result(tweet_ids: list[str], tweets: list[str], articles: list) -> None:
    """投稿結果を保存する"""
    result = {
        "date": date.today().isoformat(),
        "tweet_ids": tweet_ids,
        "tweets": tweets,
        "articles_used": [a.to_dict() for a in articles],
    }
    save_json(result, "posts", f"{date.today()}.json")


def cleanup_old_data() -> None:
    """古いデータファイルを削除する"""
    from config.settings import DATA_RETENTION_DAYS

    cutoff = date.today() - timedelta(days=DATA_RETENTION_DAYS)
    for subdir in ["raw", "filtered", "posts"]:
        dir_path = DATA_DIR / subdir
        if not dir_path.exists():
            continue
        for f in dir_path.glob("*.json"):
            try:
                file_date = date.fromisoformat(f.stem)
                if file_date < cutoff:
                    f.unlink()
                    logger.info(f"古いデータ削除: {f}")
            except ValueError:
                pass


async def run(dry_run: bool = False) -> None:
    """メインパイプライン実行"""
    logger.info("=== Xrunning パイプライン開始 ===")

    # 1. 収集
    logger.info("--- ステップ1: 情報収集 ---")
    articles = await collect_all()
    if not articles:
        logger.warning("記事が0件のため処理を中断します")
        return

    save_json(
        [a.to_dict() for a in articles],
        "raw",
        f"{date.today()}.json",
    )
    logger.info(f"収集完了: 合計{len(articles)}件")

    # 2. フィルタリング
    logger.info("--- ステップ2: フィルタリング ---")
    since = datetime.now(JST) - timedelta(hours=36)
    filtered = [a for a in articles if a.published >= since]
    logger.info(f"日付フィルタ後: {len(filtered)}件")

    filtered = filter_by_keywords(filtered)
    logger.info(f"キーワードフィルタ後: {len(filtered)}件")

    filtered = deduplicate(filtered)
    logger.info(f"重複排除後: {len(filtered)}件")

    if len(filtered) < 2:
        logger.warning("フィルタ後の記事が2件未満のため処理を中断します")
        return

    # 3. スコアリング
    scored = score_articles(filtered)
    top_articles = scored[:MAX_ARTICLES_FOR_AI]

    save_json(
        [a.to_dict() for a in top_articles],
        "filtered",
        f"{date.today()}.json",
    )
    logger.info(f"上位{len(top_articles)}件を選出")

    # 4. AI要約
    logger.info("--- ステップ3: AI要約 ---")
    tweets = generate_thread(top_articles)

    if not tweets:
        logger.warning("AI要約が全て失敗。フォールバック生成を実行")
        tweets = build_fallback_thread(top_articles[:5])

    tweets = validate_thread(tweets)
    logger.info(f"スレッド生成完了: {len(tweets)}ツイート")

    for i, tweet in enumerate(tweets, 1):
        logger.info(f"  Tweet {i} ({len(tweet)}文字): {tweet[:50]}...")

    # 5. 投稿
    if dry_run:
        logger.info("--- [DRY RUN] 投稿をスキップ ---")
        for i, tweet in enumerate(tweets, 1):
            logger.info(f"\n=== Tweet {i}/{len(tweets)} ===\n{tweet}")
        return

    logger.info("--- ステップ4: X投稿 ---")
    publisher = TwitterPublisher()
    tweet_ids = publisher.post_thread(tweets)

    if tweet_ids:
        save_post_result(tweet_ids, tweets, top_articles)
        logger.info(f"投稿完了: {len(tweet_ids)}ツイート")
    else:
        logger.error("投稿に失敗しました")

    # 6. クリーンアップ
    cleanup_old_data()

    logger.info("=== Xrunning パイプライン完了 ===")


def main():
    parser = argparse.ArgumentParser(description="AIニュース自動収集・X投稿システム")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="投稿せずにログ出力のみ行う",
    )
    args = parser.parse_args()

    setup_logging()

    try:
        asyncio.run(run(dry_run=args.dry_run))
    except Exception as e:
        logger.critical(f"予期しないエラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

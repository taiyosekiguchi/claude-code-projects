"""メインオーケストレーター: 収集 → フィルタ → AI要約 → X投稿"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import DATA_DIR, LOG_DIR, MAX_ARTICLES_FOR_AI, THREAD_MAX_TWEETS
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

# 投稿状態ファイル（その日の投稿が完了したかを管理）
STATUS_FILE = DATA_DIR / "cache" / "post_status.json"


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


def load_post_status() -> dict:
    """投稿状態を読み込む"""
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_post_status(status: dict) -> None:
    """投稿状態を保存する"""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_post_complete_today() -> bool:
    """今日の投稿が全ツイート成功済みかチェック"""
    status = load_post_status()
    today = date.today().isoformat()
    return status.get("date") == today and status.get("complete", False)


def mark_post_complete() -> None:
    """今日の投稿を完了としてマーク"""
    save_post_status({
        "date": date.today().isoformat(),
        "complete": True,
    })


def mark_post_failed(tweet_ids: list[str], tweets: list[str], retry_count: int) -> None:
    """今日の投稿が未完了であることを記録（リトライ用データ保存）"""
    save_post_status({
        "date": date.today().isoformat(),
        "complete": False,
        "posted_ids": tweet_ids,
        "all_tweets": tweets,
        "last_retry": retry_count,
    })


def clear_failed_post() -> None:
    """失敗した投稿データを消去する"""
    save_post_status({
        "date": date.today().isoformat(),
        "complete": True,  # あきらめたのでcomplete扱い（再実行しない）
        "gave_up": True,
    })


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
    """メインパイプライン実行（朝8時の初回実行）"""
    logger.info("=== Xrunning パイプライン開始 ===")

    # 既に今日の投稿が完了していればスキップ
    if is_post_complete_today():
        logger.info("今日の投稿は既に完了しています。スキップ")
        return

    # 1. 収集
    logger.info("--- ステップ1: 情報収集 ---")
    articles = await collect_all()
    if not articles:
        logger.warning("記事が0件のため処理を中断します（ネットワーク障害の可能性）。リトライ待ち状態に設定")
        save_post_status({
            "date": date.today().isoformat(),
            "complete": False,
            "collection_failed": True,
            "posted_ids": [],
            "all_tweets": [],
            "last_retry": 0,
        })
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

    if tweet_ids and len(tweet_ids) == len(tweets):
        # 全ツイート成功
        save_post_result(tweet_ids, tweets, top_articles)
        mark_post_complete()
        logger.info(f"投稿完了: {len(tweet_ids)}/{len(tweets)}ツイート（全て成功）")
    elif tweet_ids:
        # 一部成功 → リトライ用に保存
        save_post_result(tweet_ids, tweets, top_articles)
        mark_post_failed(tweet_ids, tweets, retry_count=0)
        logger.warning(f"投稿一部成功: {len(tweet_ids)}/{len(tweets)}ツイート。昼・夜にリトライ予定")
    else:
        # 全て失敗 → リトライ用に保存
        mark_post_failed([], tweets, retry_count=0)
        logger.error("投稿に全て失敗しました。昼・夜にリトライ予定")

    # 6. クリーンアップ
    cleanup_old_data()

    logger.info("=== Xrunning パイプライン完了 ===")


async def run_retry() -> None:
    """リトライ実行（昼12時・夜20時）"""
    logger.info("=== Xrunning リトライ実行 ===")

    # 今日の投稿が完了済みならスキップ
    if is_post_complete_today():
        logger.info("今日の投稿は完了済み。リトライ不要")
        return

    # 未完了の投稿データを読み込む
    status = load_post_status()
    today = date.today().isoformat()

    if status.get("date") != today:
        logger.info("今日の投稿データがありません。リトライ不要")
        return

    # 収集失敗（ネットワーク障害など）の場合はフルパイプラインを再実行
    if status.get("collection_failed"):
        logger.info("前回収集失敗のため、収集からやり直します")
        await run()
        return

    posted_ids = status.get("posted_ids", [])
    all_tweets = status.get("all_tweets", [])
    last_retry = status.get("last_retry", 0)

    if not all_tweets:
        logger.info("リトライ対象のツイートがありません")
        return

    # 残りのツイートを特定
    remaining_tweets = all_tweets[len(posted_ids):]
    if not remaining_tweets:
        logger.info("全ツイート投稿済み")
        mark_post_complete()
        return

    retry_count = last_retry + 1
    logger.info(f"リトライ {retry_count}回目: 残り{len(remaining_tweets)}ツイートを投稿")

    # 最後の投稿済みツイートIDを取得（リプライチェーン用）
    reply_to = posted_ids[-1] if posted_ids else None

    publisher = TwitterPublisher()
    import time
    new_ids = []

    for i, tweet_text in enumerate(remaining_tweets):
        num = len(posted_ids) + i + 1
        total = len(all_tweets)
        tweet_id = publisher._post_single(tweet_text, reply_to, num, total)

        if tweet_id is None:
            logger.error(f"リトライ: ツイート{num}/{total}の投稿に失敗")
            break

        new_ids.append(tweet_id)
        reply_to = tweet_id
        logger.info(f"リトライ投稿成功 [{num}/{total}]: id={tweet_id}")

        if i < len(remaining_tweets) - 1:
            time.sleep(15)

    # 結果を更新
    all_posted_ids = posted_ids + new_ids

    if len(all_posted_ids) == len(all_tweets):
        # 全ツイート成功
        mark_post_complete()
        logger.info(f"リトライ成功: 全{len(all_tweets)}ツイート投稿完了")
    elif retry_count >= 2:
        # 2回リトライしてもダメ → あきらめて消去
        clear_failed_post()
        logger.warning(
            f"リトライ{retry_count}回失敗。本日の投稿をあきらめます。"
            f"（{len(all_posted_ids)}/{len(all_tweets)}ツイートのみ投稿済み）"
        )
    else:
        # まだリトライ回数が残っている
        mark_post_failed(all_posted_ids, all_tweets, retry_count)
        logger.warning(
            f"リトライ{retry_count}回目失敗: {len(all_posted_ids)}/{len(all_tweets)}ツイート。"
            f"次のリトライで再試行予定"
        )

    logger.info("=== Xrunning リトライ完了 ===")


def main():
    parser = argparse.ArgumentParser(description="AIニュース自動収集・X投稿システム")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="投稿せずにログ出力のみ行う",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="朝の投稿が未完了の場合にリトライする",
    )
    args = parser.parse_args()

    setup_logging()

    try:
        if args.retry:
            asyncio.run(run_retry())
        else:
            asyncio.run(run(dry_run=args.dry_run))
    except Exception as e:
        logger.critical(f"予期しないエラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

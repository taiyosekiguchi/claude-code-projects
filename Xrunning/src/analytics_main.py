"""分析パイプラインオーケストレータ: スクレイピング → DB保存 → 集約 → レポート"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import (
    ANALYTICS_DB_PATH,
    DATA_DIR,
    LOG_DIR,
    SCRAPE_DELAY_BETWEEN_TWEETS,
    X_USERNAME,
)
from src.analytics.engagement_db import EngagementDB
from src.analytics.scraper import TweetMetricsScraper

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("xrunning.analytics")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger("xrunning")
    if root_logger.handlers:
        return  # 既にセットアップ済み

    root_logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        LOG_DIR / f"analytics_{date.today()}.log",
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

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def load_post_data(target_date: str) -> dict | None:
    """指定日の投稿データを読み込む"""
    post_file = DATA_DIR / "posts" / f"{target_date}.json"
    if not post_file.exists():
        return None
    try:
        with open(post_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"投稿データ読み込み失敗 ({target_date}): {e}")
        return None


def get_dates_to_scrape() -> list[tuple[str, str]]:
    """スクレイピング対象の日付とスナップショットタイプを決定する

    Returns:
        [(thread_date, snapshot_type), ...]
    """
    now = datetime.now(JST)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()

    targets = []

    hour = now.hour

    if hour < 10:
        # 07:50 実行: 昨日のT+24h、一昨日のT+48h
        if load_post_data(yesterday):
            targets.append((yesterday, "24h"))
        if load_post_data(two_days_ago):
            targets.append((two_days_ago, "48h"))
    elif hour < 12:
        # 09:00 実行: 今日のT+1h
        if load_post_data(today):
            targets.append((today, "1h"))
    elif hour < 18:
        # 14:00 実行: 今日のT+6h
        if load_post_data(today):
            targets.append((today, "6h"))
    else:
        # それ以外: 今日のデータがあればスクレイピング
        if load_post_data(today):
            targets.append((today, "late"))

    return targets


async def run_scraping(db: EngagementDB, skip_scrape: bool = False) -> None:
    """スクレイピングを実行してDBに保存"""
    targets = get_dates_to_scrape()

    if not targets:
        logger.info("スクレイピング対象がありません")
        return

    for thread_date, snapshot_type in targets:
        post_data = load_post_data(thread_date)
        if not post_data:
            continue

        tweet_ids = post_data.get("tweet_ids", [])
        if not tweet_ids:
            logger.warning(f"{thread_date}: tweet_idsがありません")
            continue

        # 既にこのスナップショットが存在するかチェック
        existing = db.get_snapshots(thread_date)
        existing_types = {(s["tweet_id"], s["snapshot_type"]) for s in existing}
        need_scrape = any(
            (tid, snapshot_type) not in existing_types for tid in tweet_ids
        )

        if not need_scrape:
            logger.info(f"{thread_date}/{snapshot_type}: 既にスクレイピング済み")
            continue

        if skip_scrape:
            logger.info(f"[SKIP] {thread_date}/{snapshot_type}: --skip-scrape が指定されています")
            continue

        logger.info(f"スクレイピング開始: {thread_date} ({snapshot_type}), {len(tweet_ids)}ツイート")

        try:
            async with TweetMetricsScraper(
                delay_between_tweets=SCRAPE_DELAY_BETWEEN_TWEETS
            ) as scraper:
                results = await scraper.scrape_thread(tweet_ids, X_USERNAME)

                for position, (tweet_id, metrics) in enumerate(results, 1):
                    if metrics:
                        db.save_snapshot(
                            tweet_id=tweet_id,
                            thread_date=thread_date,
                            position=position,
                            snapshot_type=snapshot_type,
                            metrics=metrics.to_dict(),
                        )
                    else:
                        logger.warning(f"メトリクス取得失敗: tweet_id={tweet_id}")

                # フォロワー数も取得
                follower_data = await scraper.scrape_follower_count(X_USERNAME)
                if follower_data:
                    followers, following = follower_data
                    db.log_follower_count(followers, following, source="scraped")

        except Exception as e:
            logger.error(f"スクレイピングエラー ({thread_date}): {e}", exc_info=True)

    # 日次集約を更新
    for thread_date, _ in targets:
        try:
            db.update_daily_aggregate(thread_date)
        except Exception as e:
            logger.error(f"日次集約更新エラー ({thread_date}): {e}")


def update_topic_data(db: EngagementDB) -> None:
    """投稿データとメトリクスからトピック別パフォーマンスを更新"""
    # 直近30日分のスレッドを対象
    for days_ago in range(30):
        target_date = (date.today() - timedelta(days=days_ago)).isoformat()
        post_data = load_post_data(target_date)
        if not post_data:
            continue

        articles = post_data.get("articles_used", [])
        snapshots = db.get_snapshots(target_date)
        if not snapshots:
            continue

        # ポジションごとのメトリクスを集約
        pos_metrics = {}
        for s in snapshots:
            pos = s["position_in_thread"]
            if pos not in pos_metrics or s["scraped_at"] > pos_metrics[pos]["scraped_at"]:
                pos_metrics[pos] = s

        # 記事のキーワードをトピックとしてマッピング
        # ツイート2-4番目が記事に対応（1=イントロ、5=まとめ）
        for i, article in enumerate(articles[:3]):
            tweet_pos = i + 2  # 記事ツイートは2番目から
            metrics = pos_metrics.get(tweet_pos)
            if not metrics:
                continue

            keywords = article.get("keywords", [])
            for keyword in keywords:
                keyword_lower = keyword.lower().strip()
                if len(keyword_lower) < 2:
                    continue
                try:
                    db.save_topic_performance(
                        topic=keyword_lower,
                        thread_date=target_date,
                        tweet_position=tweet_pos,
                        views=metrics["views"],
                        likes=metrics["likes"],
                        retweets=metrics["retweets"],
                    )
                except Exception as e:
                    logger.debug(f"トピック保存エラー ({keyword_lower}): {e}")


def generate_reports(db: EngagementDB) -> None:
    """レポートを生成（日曜日に週次レポート生成）"""
    now = datetime.now(JST)

    # 週次テキストレポート（日曜のみ）
    if now.weekday() == 6:  # 日曜日
        try:
            from src.analytics.report_generator import ReportGenerator

            generator = ReportGenerator(db)
            text_report = generator.generate_weekly_text_report()
            logger.info(f"\n{text_report}")

            html_path = generator.generate_dashboard()
            logger.info(f"ダッシュボード生成: {html_path}")
        except ImportError:
            logger.debug("ReportGenerator未実装。Phase 2で追加予定")
        except Exception as e:
            logger.error(f"レポート生成エラー: {e}", exc_info=True)
    else:
        # 日曜以外でもダッシュボードは更新
        try:
            from src.analytics.report_generator import ReportGenerator

            generator = ReportGenerator(db)
            html_path = generator.generate_dashboard()
            logger.info(f"ダッシュボード更新: {html_path}")
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"ダッシュボード更新エラー: {e}")


async def run_analytics(
    skip_scrape: bool = False,
    test_mode: bool = False,
    report_only: bool = False,
) -> None:
    """分析パイプライン実行"""
    logger.info("=== Xrunning 分析パイプライン開始 ===")

    db = EngagementDB(ANALYTICS_DB_PATH)

    if report_only:
        logger.info("--- レポート生成モード ---")
        generate_reports(db)
        logger.info("=== 分析パイプライン完了 ===")
        return

    if test_mode:
        logger.info("--- テストモード: 直近の投稿をスクレイピング ---")
        # テストモードでは今日 or 昨日のデータを強制スクレイピング
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        post_data = load_post_data(today) or load_post_data(yesterday)

        if not post_data:
            logger.error("テスト用の投稿データがありません")
            return

        tweet_ids = post_data.get("tweet_ids", [])
        test_date = post_data.get("date", today)

        if not tweet_ids:
            logger.error("tweet_idsがありません")
            return

        logger.info(f"テスト対象: {test_date}, {len(tweet_ids)}ツイート")

        try:
            async with TweetMetricsScraper(
                delay_between_tweets=SCRAPE_DELAY_BETWEEN_TWEETS
            ) as scraper:
                results = await scraper.scrape_thread(tweet_ids, X_USERNAME)

                for position, (tweet_id, metrics) in enumerate(results, 1):
                    if metrics:
                        db.save_snapshot(
                            tweet_id=tweet_id,
                            thread_date=test_date,
                            position=position,
                            snapshot_type="test",
                            metrics=metrics.to_dict(),
                        )
                        logger.info(f"  [{position}] views={metrics.views}, likes={metrics.likes}, RT={metrics.retweets}")
                    else:
                        logger.warning(f"  [{position}] メトリクス取得失敗")

                # フォロワー数
                follower_data = await scraper.scrape_follower_count(X_USERNAME)
                if follower_data:
                    followers, following = follower_data
                    db.log_follower_count(followers, following, source="test")
                    logger.info(f"フォロワー: {followers}, フォロー: {following}")

        except Exception as e:
            logger.error(f"テストスクレイピングエラー: {e}", exc_info=True)

        logger.info("=== テスト完了 ===")
        return

    # 通常実行
    # 1. スクレイピング
    logger.info("--- ステップ1: メトリクス収集 ---")
    await run_scraping(db, skip_scrape=skip_scrape)

    # 2. トピックデータ更新
    logger.info("--- ステップ2: トピック分析更新 ---")
    update_topic_data(db)

    # 3. レポート生成
    logger.info("--- ステップ3: レポート ---")
    generate_reports(db)

    # 4. CSV インポート（ディレクトリにファイルがあれば）
    logger.info("--- ステップ4: CSVインポート確認 ---")
    try:
        from src.analytics.csv_importer import import_pending_csvs

        imported = import_pending_csvs(db)
        if imported > 0:
            logger.info(f"CSVインポート: {imported}件")
    except ImportError:
        logger.debug("CSVImporter未実装。Phase 2で追加予定")
    except Exception as e:
        logger.error(f"CSVインポートエラー: {e}")

    logger.info("=== Xrunning 分析パイプライン完了 ===")


def main():
    parser = argparse.ArgumentParser(description="Xrunning 分析パイプライン")
    parser.add_argument(
        "--test",
        action="store_true",
        help="テストモード: 直近の投稿をスクレイピングして結果表示",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="スクレイピングをスキップ（DB/レポート処理のみ）",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="レポート生成のみ実行",
    )
    args = parser.parse_args()

    setup_logging()

    try:
        asyncio.run(
            run_analytics(
                skip_scrape=args.skip_scrape,
                test_mode=args.test,
                report_only=args.report,
            )
        )
    except Exception as e:
        logger.critical(f"予期しないエラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

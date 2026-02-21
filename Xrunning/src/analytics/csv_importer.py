"""X Analytics CSV インポーター（フォールバック用）"""

import csv
import logging
from datetime import datetime
from pathlib import Path

from config.settings import ANALYTICS_IMPORT_DIR
from src.analytics.engagement_db import EngagementDB

logger = logging.getLogger("xrunning.analytics.csv_importer")


def import_csv(db: EngagementDB, csv_path: Path) -> int:
    """X Analytics のCSVエクスポートをインポート

    X Analytics の CSV は以下のようなカラムを含む:
    - Tweet id
    - Tweet permalink
    - impressions
    - engagements
    - engagement rate
    - retweets
    - replies
    - likes
    - user profile clicks
    - url clicks
    - hashtag clicks
    - detail expands

    Returns:
        インポートされたレコード数
    """
    imported = 0

    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tweet_id = row.get("Tweet id", "").strip()
                if not tweet_id:
                    continue

                # パーマリンクから日付を推定（難しい場合はインポート日を使用）
                permalink = row.get("Tweet permalink", "")
                thread_date = _extract_date_from_permalink(permalink)

                views = _safe_int(row.get("impressions", "0"))
                likes = _safe_int(row.get("likes", "0"))
                retweets = _safe_int(row.get("retweets", "0"))
                replies = _safe_int(row.get("replies", "0"))

                metrics = {
                    "views": views,
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                    "quotes": 0,
                    "bookmarks": 0,
                }

                db.save_snapshot(
                    tweet_id=tweet_id,
                    thread_date=thread_date,
                    position=0,  # CSV からはポジション不明
                    snapshot_type="csv_import",
                    metrics=metrics,
                )
                imported += 1

    except Exception as e:
        logger.error(f"CSVインポートエラー ({csv_path.name}): {e}")

    return imported


def import_pending_csvs(db: EngagementDB) -> int:
    """analytics_import/ ディレクトリ内のCSVファイルを全てインポート"""
    import_dir = Path(ANALYTICS_IMPORT_DIR)
    if not import_dir.exists():
        return 0

    total = 0
    for csv_file in import_dir.glob("*.csv"):
        logger.info(f"CSVインポート中: {csv_file.name}")
        count = import_csv(db, csv_file)
        total += count

        # インポート済みファイルを .imported にリネーム
        if count > 0:
            done_path = csv_file.with_suffix(".csv.imported")
            csv_file.rename(done_path)
            logger.info(f"  {count}件インポート → {done_path.name}")

    return total


def _safe_int(value: str) -> int:
    try:
        return int(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _extract_date_from_permalink(permalink: str) -> str:
    """パーマリンクから日付を推定（失敗時は今日の日付）"""
    # パーマリンク例: https://twitter.com/user/status/1234567890
    # tweet_id から日付を推定（Snowflake ID）
    try:
        parts = permalink.rstrip("/").split("/")
        tweet_id = int(parts[-1])
        # Twitter Snowflake: (tweet_id >> 22) + 1288834974657 = Unix timestamp (ms)
        timestamp_ms = (tweet_id >> 22) + 1288834974657
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")

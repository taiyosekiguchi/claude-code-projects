"""SQLite データベースインターフェース: エンゲージメント分析データの永続化"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("xrunning.analytics.db")

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- メトリクスのスナップショット（不変ログ）
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL,
    thread_date TEXT NOT NULL,
    position_in_thread INTEGER NOT NULL,
    snapshot_type TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    bookmarks INTEGER DEFAULT 0,
    UNIQUE(tweet_id, snapshot_type)
);

-- 日次スレッドパフォーマンス集約
CREATE TABLE IF NOT EXISTS daily_thread_metrics (
    thread_date TEXT PRIMARY KEY,
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    total_retweets INTEGER DEFAULT 0,
    total_replies INTEGER DEFAULT 0,
    total_quotes INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0.0,
    top_tweet_position INTEGER,
    content_style TEXT DEFAULT '{}',
    topics_covered TEXT DEFAULT '[]',
    updated_at TEXT NOT NULL
);

-- トピック別パフォーマンス
CREATE TABLE IF NOT EXISTS topic_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    thread_date TEXT NOT NULL,
    tweet_position INTEGER,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0.0,
    UNIQUE(topic, thread_date, tweet_position)
);

-- A/B テスト記録
CREATE TABLE IF NOT EXISTS style_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_date TEXT NOT NULL UNIQUE,
    variant_name TEXT NOT NULL,
    experiment_name TEXT NOT NULL DEFAULT '',
    variant_params TEXT NOT NULL DEFAULT '{}',
    engagement_rate REAL DEFAULT 0.0,
    views INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- フォロワー推移
CREATE TABLE IF NOT EXISTS follower_log (
    date TEXT PRIMARY KEY,
    follower_count INTEGER NOT NULL,
    following_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'scraped'
);

-- 週次サマリ
CREATE TABLE IF NOT EXISTS weekly_summary (
    week_start TEXT PRIMARY KEY,
    avg_views REAL DEFAULT 0.0,
    avg_likes REAL DEFAULT 0.0,
    avg_retweets REAL DEFAULT 0.0,
    avg_engagement_rate REAL DEFAULT 0.0,
    total_threads INTEGER DEFAULT 0,
    best_topic TEXT,
    best_style TEXT,
    follower_count_start INTEGER,
    follower_count_end INTEGER,
    estimated_monthly_impressions REAL DEFAULT 0.0
);

-- スキーマバージョン管理
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class EngagementDB:
    """エンゲージメント分析データの SQLite ラッパー"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # バージョン記録
            existing = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
        logger.debug(f"DB初期化完了: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # === スナップショット ===

    def save_snapshot(
        self,
        tweet_id: str,
        thread_date: str,
        position: int,
        snapshot_type: str,
        metrics: dict,
    ) -> None:
        """メトリクスのスナップショットを保存（UPSERT）"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO metric_snapshots
                    (tweet_id, thread_date, position_in_thread,
                     snapshot_type, scraped_at, views, likes,
                     retweets, replies, quotes, bookmarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tweet_id, snapshot_type) DO UPDATE SET
                    views=excluded.views,
                    likes=excluded.likes,
                    retweets=excluded.retweets,
                    replies=excluded.replies,
                    quotes=excluded.quotes,
                    bookmarks=excluded.bookmarks,
                    scraped_at=excluded.scraped_at
                """,
                (
                    tweet_id,
                    thread_date,
                    position,
                    snapshot_type,
                    datetime.now().isoformat(),
                    metrics.get("views", 0),
                    metrics.get("likes", 0),
                    metrics.get("retweets", 0),
                    metrics.get("replies", 0),
                    metrics.get("quotes", 0),
                    metrics.get("bookmarks", 0),
                ),
            )
        logger.debug(f"スナップショット保存: tweet={tweet_id}, type={snapshot_type}")

    def get_snapshots(self, thread_date: str) -> list[dict]:
        """指定日のスナップショットを全て取得"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM metric_snapshots WHERE thread_date = ? ORDER BY position_in_thread, snapshot_type",
                (thread_date,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_snapshot(self, tweet_id: str) -> dict | None:
        """指定ツイートの最新スナップショットを取得"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM metric_snapshots
                   WHERE tweet_id = ?
                   ORDER BY scraped_at DESC LIMIT 1""",
                (tweet_id,),
            ).fetchone()
        return dict(row) if row else None

    # === 日次集約 ===

    def update_daily_aggregate(self, thread_date: str) -> None:
        """最新のスナップショットから日次集約を再計算"""
        with self._connect() as conn:
            # 各ツイートの最新スナップショットを集計
            rows = conn.execute(
                """
                SELECT position_in_thread,
                       MAX(views) as views, MAX(likes) as likes,
                       MAX(retweets) as retweets, MAX(replies) as replies,
                       MAX(quotes) as quotes
                FROM metric_snapshots
                WHERE thread_date = ?
                GROUP BY tweet_id
                """,
                (thread_date,),
            ).fetchall()

            if not rows:
                return

            total_views = sum(r["views"] for r in rows)
            total_likes = sum(r["likes"] for r in rows)
            total_retweets = sum(r["retweets"] for r in rows)
            total_replies = sum(r["replies"] for r in rows)
            total_quotes = sum(r["quotes"] for r in rows)

            engagement = total_likes + total_retweets + total_replies + total_quotes
            er = (engagement / total_views * 100) if total_views > 0 else 0.0

            # 最もエンゲージメントが高いツイートのポジション
            best_pos = max(rows, key=lambda r: r["likes"] + r["retweets"])["position_in_thread"]

            conn.execute(
                """
                INSERT INTO daily_thread_metrics
                    (thread_date, total_views, total_likes, total_retweets,
                     total_replies, total_quotes, engagement_rate,
                     top_tweet_position, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_date) DO UPDATE SET
                    total_views=excluded.total_views,
                    total_likes=excluded.total_likes,
                    total_retweets=excluded.total_retweets,
                    total_replies=excluded.total_replies,
                    total_quotes=excluded.total_quotes,
                    engagement_rate=excluded.engagement_rate,
                    top_tweet_position=excluded.top_tweet_position,
                    updated_at=excluded.updated_at
                """,
                (
                    thread_date,
                    total_views,
                    total_likes,
                    total_retweets,
                    total_replies,
                    total_quotes,
                    round(er, 4),
                    best_pos,
                    datetime.now().isoformat(),
                ),
            )
        logger.info(f"日次集約更新: {thread_date} (views={total_views}, ER={er:.2f}%)")

    def get_daily_metrics(self, thread_date: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_thread_metrics WHERE thread_date = ?",
                (thread_date,),
            ).fetchone()
        return dict(row) if row else None

    def get_daily_metrics_range(self, days: int = 30) -> list[dict]:
        """直近N日の日次集約を取得"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM daily_thread_metrics
                   ORDER BY thread_date DESC LIMIT ?""",
                (days,),
            ).fetchall()
        return [dict(r) for r in rows]

    # === トピックパフォーマンス ===

    def save_topic_performance(
        self,
        topic: str,
        thread_date: str,
        tweet_position: int,
        views: int,
        likes: int,
        retweets: int,
    ) -> None:
        total_engagement = likes + retweets
        er = (total_engagement / views * 100) if views > 0 else 0.0
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO topic_performance
                    (topic, thread_date, tweet_position, views, likes, retweets, engagement_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic, thread_date, tweet_position) DO UPDATE SET
                    views=excluded.views, likes=excluded.likes,
                    retweets=excluded.retweets, engagement_rate=excluded.engagement_rate
                """,
                (topic, thread_date, tweet_position, views, likes, retweets, round(er, 4)),
            )

    def get_topic_performance(self, days: int = 30) -> list[dict]:
        """トピック別の平均エンゲージメント率を取得"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT topic,
                       AVG(engagement_rate) as avg_er,
                       SUM(views) as total_views,
                       COUNT(*) as count
                FROM topic_performance
                WHERE thread_date >= date('now', ? || ' days')
                GROUP BY topic
                HAVING count >= 2
                ORDER BY avg_er DESC
                """,
                (f"-{days}",),
            ).fetchall()
        return [dict(r) for r in rows]

    # === A/B テスト ===

    def save_experiment(
        self,
        thread_date: str,
        experiment_name: str,
        variant_name: str,
        variant_params: dict,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO style_experiments
                    (thread_date, experiment_name, variant_name, variant_params, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(thread_date) DO UPDATE SET
                    experiment_name=excluded.experiment_name,
                    variant_name=excluded.variant_name,
                    variant_params=excluded.variant_params
                """,
                (
                    thread_date,
                    experiment_name,
                    variant_name,
                    json.dumps(variant_params, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )

    def update_experiment_metrics(
        self, thread_date: str, engagement_rate: float, views: int
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE style_experiments
                   SET engagement_rate = ?, views = ?
                   WHERE thread_date = ?""",
                (engagement_rate, views, thread_date),
            )

    def get_experiment_results(self, experiment_name: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM style_experiments
                   WHERE experiment_name = ?
                   ORDER BY thread_date""",
                (experiment_name,),
            ).fetchall()
        return [dict(r) for r in rows]

    # === フォロワー ===

    def log_follower_count(
        self, count: int, following: int = 0, source: str = "scraped"
    ) -> None:
        today = date.today().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO follower_log (date, follower_count, following_count, source)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                       follower_count=excluded.follower_count,
                       following_count=excluded.following_count,
                       source=excluded.source""",
                (today, count, following, source),
            )
        logger.info(f"フォロワー記録: {count} ({source})")

    def get_follower_history(self, days: int = 90) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM follower_log
                   WHERE date >= date('now', ? || ' days')
                   ORDER BY date""",
                (f"-{days}",),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_follower_count(self) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT follower_count FROM follower_log ORDER BY date DESC LIMIT 1"
            ).fetchone()
        return row["follower_count"] if row else None

    # === 週次サマリ ===

    def save_weekly_summary(self, summary: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO weekly_summary
                    (week_start, avg_views, avg_likes, avg_retweets,
                     avg_engagement_rate, total_threads, best_topic,
                     best_style, follower_count_start, follower_count_end,
                     estimated_monthly_impressions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(week_start) DO UPDATE SET
                       avg_views=excluded.avg_views,
                       avg_likes=excluded.avg_likes,
                       avg_retweets=excluded.avg_retweets,
                       avg_engagement_rate=excluded.avg_engagement_rate,
                       total_threads=excluded.total_threads,
                       best_topic=excluded.best_topic,
                       best_style=excluded.best_style,
                       follower_count_start=excluded.follower_count_start,
                       follower_count_end=excluded.follower_count_end,
                       estimated_monthly_impressions=excluded.estimated_monthly_impressions""",
                (
                    summary["week_start"],
                    summary.get("avg_views", 0),
                    summary.get("avg_likes", 0),
                    summary.get("avg_retweets", 0),
                    summary.get("avg_engagement_rate", 0),
                    summary.get("total_threads", 0),
                    summary.get("best_topic"),
                    summary.get("best_style"),
                    summary.get("follower_count_start"),
                    summary.get("follower_count_end"),
                    summary.get("estimated_monthly_impressions", 0),
                ),
            )

    def get_weekly_summaries(self, weeks: int = 8) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM weekly_summary ORDER BY week_start DESC LIMIT ?",
                (weeks,),
            ).fetchall()
        return [dict(r) for r in rows]

    # === ユーティリティ ===

    def get_threads_needing_scrape(self, snapshot_type: str) -> list[dict]:
        """指定タイプのスナップショットがまだないスレッドを取得"""
        with self._connect() as conn:
            # data/posts/ のJSONから取得すべきスレッド日付を特定するのは
            # analytics_main.py の責務。ここではDBにあるデータを返す
            rows = conn.execute(
                """
                SELECT DISTINCT thread_date
                FROM metric_snapshots
                WHERE thread_date NOT IN (
                    SELECT DISTINCT thread_date FROM metric_snapshots
                    WHERE snapshot_type = ?
                )
                ORDER BY thread_date DESC LIMIT 3
                """,
                (snapshot_type,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_thread_dates(self) -> list[str]:
        """DB内の全スレッド日付を取得"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT thread_date FROM metric_snapshots ORDER BY thread_date DESC"
            ).fetchall()
        return [r["thread_date"] for r in rows]

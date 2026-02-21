"""分析エンジン: KPI算出・インサイト生成・最適化ヒント"""

import logging
from datetime import date, timedelta

from config.settings import (
    MIN_DATA_DAYS_FOR_FEEDBACK,
    TARGET_FOLLOWERS,
    TARGET_IMPRESSIONS_3MO,
    TOPIC_BOOST_LOOKBACK_DAYS,
    TOPIC_BOOST_MAX_MULTIPLIER,
    TOPIC_BOOST_MIN_MULTIPLIER,
)
from src.analytics.engagement_db import EngagementDB

logger = logging.getLogger("xrunning.analytics.analyzer")


class EngagementAnalyzer:
    """エンゲージメントデータからKPIとインサイトを生成"""

    def __init__(self, db: EngagementDB):
        self.db = db

    # === 基本KPI ===

    def has_enough_data(self) -> bool:
        """フィードバックループを起動するのに十分なデータがあるか"""
        metrics = self.db.get_daily_metrics_range(days=MIN_DATA_DAYS_FOR_FEEDBACK)
        # views > 0 のデータが閾値以上あるか
        valid_days = sum(1 for m in metrics if m.get("total_views", 0) > 0)
        return valid_days >= MIN_DATA_DAYS_FOR_FEEDBACK

    def get_engagement_rate(self, thread_date: str) -> float:
        """指定日のエンゲージメント率を取得"""
        metrics = self.db.get_daily_metrics(thread_date)
        if not metrics:
            return 0.0
        return metrics.get("engagement_rate", 0.0)

    def get_avg_engagement_rate(self, days: int = 30) -> float:
        """直近N日の平均エンゲージメント率"""
        metrics = self.db.get_daily_metrics_range(days=days)
        if not metrics:
            return 0.0
        rates = [m["engagement_rate"] for m in metrics if m["engagement_rate"] > 0]
        return sum(rates) / len(rates) if rates else 0.0

    def get_avg_views(self, days: int = 7) -> float:
        """直近N日の平均ビュー数"""
        metrics = self.db.get_daily_metrics_range(days=days)
        if not metrics:
            return 0.0
        views = [m["total_views"] for m in metrics if m["total_views"] > 0]
        return sum(views) / len(views) if views else 0.0

    # === トピック分析 ===

    def get_best_topics(self, days: int = None) -> list[dict]:
        """エンゲージメント率の高いトピックを取得"""
        if days is None:
            days = TOPIC_BOOST_LOOKBACK_DAYS
        return self.db.get_topic_performance(days=days)

    def get_topic_boosts(self) -> dict[str, float]:
        """トピック別のスコアリングブースト値を算出

        Returns:
            {"claude": 1.5, "openai": 1.2, "hardware": 0.7, ...}
        """
        topics = self.get_best_topics()
        if not topics:
            return {}

        # 平均ERを算出
        all_ers = [t["avg_er"] for t in topics if t["avg_er"] > 0]
        if not all_ers:
            return {}

        avg_er = sum(all_ers) / len(all_ers)
        if avg_er == 0:
            return {}

        boosts = {}
        for topic_data in topics:
            topic = topic_data["topic"]
            er = topic_data["avg_er"]

            # 平均との比率でブースト値を決定
            ratio = er / avg_er
            boost = max(TOPIC_BOOST_MIN_MULTIPLIER, min(TOPIC_BOOST_MAX_MULTIPLIER, ratio))
            boosts[topic] = round(boost, 2)

        return boosts

    # === スレッド構造分析 ===

    def get_best_tweet_position(self) -> dict[int, float]:
        """スレッド内のポジション別の平均エンゲージメント

        Returns:
            {1: 0.5, 2: 3.2, 3: 2.8, 4: 1.5, 5: 2.0}
        """
        metrics_list = self.db.get_daily_metrics_range(days=30)
        if not metrics_list:
            return {}

        # 各日のスナップショットからポジション別データを集計
        position_data: dict[int, list[float]] = {}

        for daily in metrics_list:
            snapshots = self.db.get_snapshots(daily["thread_date"])
            # 各ポジションの最新スナップショット
            pos_latest: dict[int, dict] = {}
            for s in snapshots:
                pos = s["position_in_thread"]
                if pos not in pos_latest or s["scraped_at"] > pos_latest[pos]["scraped_at"]:
                    pos_latest[pos] = s

            for pos, s in pos_latest.items():
                views = s.get("views", 0)
                if views == 0:
                    continue
                engagement = s.get("likes", 0) + s.get("retweets", 0) + s.get("replies", 0)
                er = engagement / views * 100
                position_data.setdefault(pos, []).append(er)

        return {
            pos: round(sum(ers) / len(ers), 2)
            for pos, ers in sorted(position_data.items())
            if ers
        }

    # === ハッシュタグ分析 ===

    def get_hashtag_effectiveness(self) -> list[dict]:
        """ハッシュタグの効果分析（将来的に実装拡張）

        現状はトピックパフォーマンスをベースに推定。
        ハッシュタグの直接的な追跡は将来のA/Bテストで実施。
        """
        # ハッシュタグはまとめツイート（最後のツイート）に含まれるため、
        # 個別のハッシュタグ効果の測定は困難。
        # A/Bテストで間接的に評価する
        return []

    # === 成長分析 ===

    def get_growth_velocity(self) -> dict:
        """成長速度とマイルストーン予測"""
        history = self.db.get_follower_history(days=90)
        current_followers = self.db.get_latest_follower_count() or 0

        result = {
            "current_followers": current_followers,
            "target_followers": TARGET_FOLLOWERS,
            "followers_pct": round(current_followers / TARGET_FOLLOWERS * 100, 1) if TARGET_FOLLOWERS > 0 else 0,
            "daily_follower_growth": 0.0,
            "est_days_to_500": None,
            "monthly_impressions": 0.0,
            "est_months_to_5m": None,
        }

        # フォロワー成長率
        if len(history) >= 2:
            first = history[0]
            last = history[-1]
            days_diff = (
                date.fromisoformat(last["date"]) - date.fromisoformat(first["date"])
            ).days
            if days_diff > 0:
                follower_diff = last["follower_count"] - first["follower_count"]
                daily_growth = follower_diff / days_diff
                result["daily_follower_growth"] = round(daily_growth, 2)

                remaining = TARGET_FOLLOWERS - current_followers
                if daily_growth > 0 and remaining > 0:
                    result["est_days_to_500"] = int(remaining / daily_growth)

        # 月間インプレッション推定
        avg_daily_views = self.get_avg_views(days=7)
        monthly_impressions = avg_daily_views * 30
        result["monthly_impressions"] = round(monthly_impressions, 0)

        # 5Mインプレッション/3ヶ月への予測
        impressions_per_3mo = monthly_impressions * 3
        if impressions_per_3mo > 0:
            ratio = TARGET_IMPRESSIONS_3MO / impressions_per_3mo
            result["est_months_to_5m"] = round(ratio * 3, 1) if ratio > 1 else 0
        result["impressions_3mo_current"] = round(impressions_per_3mo, 0)
        result["impressions_3mo_target"] = TARGET_IMPRESSIONS_3MO
        result["impressions_pct"] = round(
            impressions_per_3mo / TARGET_IMPRESSIONS_3MO * 100, 2
        ) if TARGET_IMPRESSIONS_3MO > 0 else 0

        return result

    # === 最適化ヒント生成 ===

    def generate_optimization_hints(self) -> dict:
        """プロンプトオプティマイザーに渡す最適化ヒントを生成

        Returns:
            {
                "preferred_topics": [("claude", 4.2), ("ai agent", 3.8)],
                "avoid_topics": [("hardware", 0.5)],
                "style_hints": ["質問CTAが効果的", ...],
                "hashtag_recommendations": ["#Claude", "#AIエージェント"],
                "data_days": 21,
            }
        """
        if not self.has_enough_data():
            logger.info("データ不足のため最適化ヒントをスキップ")
            return {}

        hints: dict = {"data_days": 0}

        # データ日数
        metrics = self.db.get_daily_metrics_range(days=60)
        hints["data_days"] = len([m for m in metrics if m.get("total_views", 0) > 0])

        # トピック推奨
        topics = self.get_best_topics()
        avg_er = self.get_avg_engagement_rate(days=30)

        preferred = []
        avoid = []
        for t in topics:
            if t["avg_er"] > avg_er * 1.3:
                preferred.append((t["topic"], round(t["avg_er"], 2)))
            elif t["avg_er"] < avg_er * 0.5:
                avoid.append((t["topic"], round(t["avg_er"], 2)))

        hints["preferred_topics"] = preferred[:5]
        hints["avoid_topics"] = avoid[:3]

        # スタイルヒント（A/Bテスト結果から）
        style_hints = []
        try:
            from src.analytics.ab_testing import ABTestManager

            ab = ABTestManager(self.db)
            winners = ab.get_completed_results()
            for result in winners:
                if result.get("winner"):
                    style_hints.append(
                        f"{result['experiment_name']}: "
                        f"'{result['winner']}' が効果的 "
                        f"(ER差: {result.get('er_diff', 0):.1f}%)"
                    )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"A/Bテスト結果取得エラー: {e}")

        hints["style_hints"] = style_hints

        # ハッシュタグ推奨（高エンゲージメントトピックから生成）
        hashtag_map = {
            "claude": "#Claude",
            "anthropic": "#Anthropic",
            "openai": "#OpenAI",
            "gpt": "#GPT",
            "gemini": "#Gemini",
            "ai agent": "#AIエージェント",
            "aiエージェント": "#AIエージェント",
            "llm": "#LLM",
            "生成ai": "#生成AI",
            "機械学習": "#機械学習",
            "mcp": "#MCP",
        }
        recommended_tags = ["#AIニュース", "#AI"]  # 常時使用
        for topic, _ in preferred:
            tag = hashtag_map.get(topic.lower())
            if tag and tag not in recommended_tags:
                recommended_tags.append(tag)

        hints["hashtag_recommendations"] = recommended_tags[:6]

        # ポジション分析
        pos_data = self.get_best_tweet_position()
        if pos_data:
            best_pos = max(pos_data, key=pos_data.get)
            hints["best_position"] = best_pos
            hints["position_data"] = pos_data

        logger.info(f"最適化ヒント生成完了: {len(preferred)}推奨トピック, {len(style_hints)}スタイルヒント")
        return hints

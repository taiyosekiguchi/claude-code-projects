"""プロンプト動的最適化: エンゲージメントデータに基づくClaude指示の自動調整"""

import logging
from datetime import date

from config.prompts import SUMMARIZE_PROMPT, CONTENT_TYPE_PROMPTS
from src.analytics.analyzer import EngagementAnalyzer
from src.analytics.engagement_db import EngagementDB

logger = logging.getLogger("xrunning.analytics.optimizer")


class PromptOptimizer:
    """エンゲージメント分析結果からClaudeへの動的プロンプトを生成"""

    def __init__(self, db: EngagementDB):
        self.db = db
        self.analyzer = EngagementAnalyzer(db)

    def build_optimized_prompt(self, articles_json: str, content_type: str = "news_thread") -> str:
        """最適化されたプロンプトを構築

        Args:
            articles_json: 記事のJSON文字列
            content_type: コンテンツタイプ（news_thread, weekly_roundup, tool_spotlight, tips_thread）

        Returns:
            動的最適化セクションを追加したプロンプト文字列
        """
        # コンテンツタイプに応じたベースプロンプトを選択
        base_template = CONTENT_TYPE_PROMPTS.get(content_type, SUMMARIZE_PROMPT)
        base = base_template.format(articles_json=articles_json)
        logger.info(f"ベースプロンプト: {content_type}")

        # データが不足している場合はベースのまま返す
        if not self.analyzer.has_enough_data():
            logger.info("データ不足のためベースプロンプトをそのまま使用")
            return base

        # 最適化ヒントを取得
        hints = self.analyzer.generate_optimization_hints()
        if not hints:
            return base

        # A/Bテスト用の追加指示
        ab_instruction = self._get_ab_test_instruction()

        # 動的セクションを構築
        optimization_section = self._build_optimization_section(hints, ab_instruction)

        if optimization_section:
            optimized = base + "\n\n" + optimization_section
            logger.info(f"最適化ヒント適用: {len(optimization_section)}文字追加")
            return optimized

        return base

    def _build_optimization_section(self, hints: dict, ab_instruction: str = "") -> str:
        """最適化指示セクションを構築"""
        lines = [
            "## パフォーマンスデータに基づく最適化指示（自動生成）",
            f"※ 過去{hints.get('data_days', 0)}日間の分析データに基づく",
            "",
        ]

        # 高エンゲージメントトピック
        preferred = hints.get("preferred_topics", [])
        if preferred:
            lines.append("### 高エンゲージメントトピック（優先的に取り上げる）")
            for topic, er in preferred[:3]:
                lines.append(f"- {topic} (平均ER: {er:.1f}%)")
            lines.append("")

        # 低エンゲージメントトピック
        avoid = hints.get("avoid_topics", [])
        if avoid:
            lines.append("### 低エンゲージメントトピック（優先度を下げる）")
            for topic, er in avoid[:2]:
                lines.append(f"- {topic} (平均ER: {er:.1f}%)")
            lines.append("")

        # スタイルヒント
        style_hints = hints.get("style_hints", [])
        if style_hints:
            lines.append("### スタイル指示")
            for hint in style_hints[:3]:
                lines.append(f"- {hint}")
            lines.append("")

        # ハッシュタグ推奨
        hashtags = hints.get("hashtag_recommendations", [])
        if hashtags:
            lines.append(f"### 推奨ハッシュタグ（最後のツイートに含める）")
            lines.append(f"- {' '.join(hashtags)}")
            lines.append("")

        # A/Bテスト指示
        if ab_instruction:
            lines.append("### 今回の実験")
            lines.append(ab_instruction)
            lines.append("")

        # 最低限の内容がなければ空文字を返す
        if len(lines) <= 3:
            return ""

        return "\n".join(lines)

    def _get_ab_test_instruction(self) -> str:
        """現在のA/Bテストバリアントの指示を取得"""
        try:
            from src.analytics.ab_testing import ABTestManager

            ab = ABTestManager(self.db)
            variant = ab.get_active_variant()
            if variant:
                return (
                    f"【A/Bテスト: {variant['experiment_name']}】"
                    f"{variant['prompt_addition']}"
                )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"A/Bテスト情報取得エラー: {e}")
        return ""

    def get_topic_boosts(self) -> dict[str, float]:
        """scorer.py に渡すトピックブースト値を取得"""
        if not self.analyzer.has_enough_data():
            return {}
        return self.analyzer.get_topic_boosts()

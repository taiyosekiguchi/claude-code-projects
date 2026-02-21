"""成長戦略マネージャー: コンテンツ多様化・曜日別コンテンツタイプ"""

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger("xrunning.analytics.growth")

JST = timezone(timedelta(hours=9))

# コンテンツタイプ定義
CONTENT_TYPES = {
    "news_thread": {
        "name": "AIニューススレッド",
        "description": "通常の日次AIニュース要約",
        "days": [0, 1, 2, 3, 4],  # 月-金
    },
    "weekly_roundup": {
        "name": "週間まとめ",
        "description": "今週のトップAIニュースを振り返る",
        "days": [5],  # 土
    },
    "tool_spotlight": {
        "name": "AIツール紹介",
        "description": "注目のAIツールを1つ深掘り紹介",
        "days": [6],  # 日（隔週）
        "alternate_week": True,
        "alternate_with": "tips_thread",
    },
    "tips_thread": {
        "name": "AI活用Tips",
        "description": "アーリーアダプター向けのAI活用テクニック",
        "days": [6],  # 日（隔週）
        "alternate_week": True,
        "alternate_with": "tool_spotlight",
    },
}


class GrowthStrategyManager:
    """コンテンツ多様化と成長戦略を管理"""

    def get_todays_content_type(self) -> str:
        """今日のコンテンツタイプを決定"""
        today = date.today()
        weekday = today.weekday()

        # 月-金: news_thread
        if weekday in CONTENT_TYPES["news_thread"]["days"]:
            return "news_thread"

        # 土: weekly_roundup
        if weekday in CONTENT_TYPES["weekly_roundup"]["days"]:
            return "weekly_roundup"

        # 日: tool_spotlight / tips_thread を隔週交互
        if weekday == 6:
            week_number = today.isocalendar()[1]
            return "tool_spotlight" if week_number % 2 == 0 else "tips_thread"

        return "news_thread"

    def get_content_type_info(self, content_type: str) -> dict:
        """コンテンツタイプの情報を取得"""
        return CONTENT_TYPES.get(content_type, CONTENT_TYPES["news_thread"])

    def suggest_engagement_actions(self) -> list[str]:
        """手動エンゲージメント向上のための提案（ダッシュボードに表示）"""
        today = date.today()
        weekday = today.weekday()

        suggestions = [
            "AIに関するトレンドのポストに積極的にリプライする",
            "AI関連アカウント（100-1000フォロワー帯）を5アカウントフォローする",
        ]

        if weekday == 0:  # 月曜
            suggestions.append("先週のベストパフォーマンス投稿を分析し、何が効果的だったか確認する")
        elif weekday == 5:  # 土曜
            suggestions.append("今週のAIニュースで最も反響が大きかった話題を引用リポストする")

        return suggestions

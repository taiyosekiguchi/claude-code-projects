"""A/B テストフレームワーク: コンテンツスタイルの効果検証"""

import logging
from datetime import date, timedelta

from config.settings import AB_TEST_VARIANT_DURATION_DAYS
from src.analytics.engagement_db import EngagementDB

logger = logging.getLogger("xrunning.analytics.ab_testing")

# 実験定義: 各実験は2つのバリアントを持ち、交互に実施
EXPERIMENTS = [
    {
        "name": "emoji_usage",
        "description": "絵文字の使用量による効果の違い",
        "variants": [
            {
                "name": "emoji_heavy",
                "prompt_addition": "各ツイートに適切な絵文字を2-3個使用してください。特に冒頭と末尾に配置すると効果的です。",
            },
            {
                "name": "emoji_minimal",
                "prompt_addition": "絵文字は1ツイート目のみに1個だけ使用してください。それ以外のツイートでは絵文字を使わないでください。",
            },
        ],
    },
    {
        "name": "cta_style",
        "description": "CTA（Call To Action）スタイルの効果の違い",
        "variants": [
            {
                "name": "question_cta",
                "prompt_addition": "最後のツイートは必ず読者への質問で締めてください（例：「皆さんはどう思いますか？」「あなたならどのAIツールを使いますか？」）。",
            },
            {
                "name": "action_cta",
                "prompt_addition": "最後のツイートでは「気になったら いいね&リポストお願いします！」のようなアクション呼びかけで締めてください。",
            },
        ],
    },
    {
        "name": "intro_style",
        "description": "イントロスタイルの効果の違い",
        "variants": [
            {
                "name": "greeting_intro",
                "prompt_addition": "1ツイート目は「おはようございます！」などの挨拶から始め、今日のハイライトを1行で予告してください。",
            },
            {
                "name": "hook_intro",
                "prompt_addition": "1ツイート目は挨拶なしで、最も衝撃的/興味深いニュースの要点をインパクトのある1行目で始めてください。",
            },
        ],
    },
    {
        "name": "depth_style",
        "description": "ニュース解説の深さの違い",
        "variants": [
            {
                "name": "brief_summary",
                "prompt_addition": "各ニュースは1-2行の簡潔な要約にとどめ、より多くのニュースを紹介してください。",
            },
            {
                "name": "deep_analysis",
                "prompt_addition": "ニュース数を2つに絞り、各ニュースについて詳しい分析と今後の影響を3-4行で述べてください。",
            },
        ],
    },
]


class ABTestManager:
    """A/B テストのライフサイクルを管理"""

    def __init__(self, db: EngagementDB):
        self.db = db

    def get_active_variant(self) -> dict | None:
        """今日のアクティブなバリアントを返す

        実験はEXPERIMENTS リストの順に実行される。
        各実験は2つのバリアントを AB_TEST_VARIANT_DURATION_DAYS 日ずつ交互に実施。
        全実験が一巡したら最初からループ。

        Returns:
            {
                "experiment_name": "emoji_usage",
                "variant_name": "emoji_heavy",
                "prompt_addition": "各ツイートに...",
            }
            or None（実験なし）
        """
        if not EXPERIMENTS:
            return None

        today = date.today()

        # 基準日（最初の実験開始日）を決定
        # 既存の実験データから開始日を推定、なければ今日を開始日とする
        base_date = self._get_experiment_start_date()
        days_since_start = (today - base_date).days

        # 1実験あたりのサイクル日数（バリアントA + バリアントB）
        cycle_per_experiment = AB_TEST_VARIANT_DURATION_DAYS * 2
        total_cycle = cycle_per_experiment * len(EXPERIMENTS)

        # 現在のサイクル位置
        position = days_since_start % total_cycle

        # どの実験のどのバリアントか計算
        experiment_index = position // cycle_per_experiment
        variant_position = (position % cycle_per_experiment) // AB_TEST_VARIANT_DURATION_DAYS
        variant_index = min(variant_position, 1)

        experiment = EXPERIMENTS[experiment_index]
        variant = experiment["variants"][variant_index]

        result = {
            "experiment_name": experiment["name"],
            "variant_name": variant["name"],
            "prompt_addition": variant["prompt_addition"],
        }

        # 今日の実験をDBに記録
        self.db.save_experiment(
            thread_date=today.isoformat(),
            experiment_name=experiment["name"],
            variant_name=variant["name"],
            variant_params={"prompt_addition": variant["prompt_addition"]},
        )

        logger.debug(
            f"A/Bテスト: {experiment['name']} / {variant['name']} "
            f"(day {days_since_start}, pos {position})"
        )
        return result

    def get_completed_results(self) -> list[dict]:
        """完了した実験の結果を取得

        Returns:
            [{
                "experiment_name": "emoji_usage",
                "winner": "emoji_heavy",
                "variant_a": {"name": "emoji_heavy", "avg_er": 3.5, "count": 7},
                "variant_b": {"name": "emoji_minimal", "avg_er": 2.1, "count": 7},
                "er_diff": 1.4,
                "significant": True,
            }, ...]
        """
        results = []

        for experiment in EXPERIMENTS:
            exp_data = self.db.get_experiment_results(experiment["name"])
            if not exp_data:
                continue

            # バリアント別に集計
            variant_stats: dict[str, list[float]] = {}
            for entry in exp_data:
                vname = entry["variant_name"]
                er = entry.get("engagement_rate", 0)
                if er > 0:
                    variant_stats.setdefault(vname, []).append(er)

            if len(variant_stats) < 2:
                continue

            # 各バリアントの平均ER
            variant_summaries = {}
            for vname, ers in variant_stats.items():
                variant_summaries[vname] = {
                    "name": vname,
                    "avg_er": sum(ers) / len(ers),
                    "count": len(ers),
                }

            variants = list(variant_summaries.values())
            if len(variants) < 2:
                continue

            # 勝者判定（50%以上の差で有意判断）
            sorted_v = sorted(variants, key=lambda v: v["avg_er"], reverse=True)
            best = sorted_v[0]
            worst = sorted_v[1]
            er_diff = best["avg_er"] - worst["avg_er"]

            # 有意性判定: 相対差50%以上 && 各バリアント5日以上のデータ
            relative_diff = er_diff / worst["avg_er"] if worst["avg_er"] > 0 else 0
            significant = relative_diff > 0.5 and best["count"] >= 5 and worst["count"] >= 5

            results.append({
                "experiment_name": experiment["name"],
                "winner": best["name"] if significant else None,
                "variant_a": sorted_v[0],
                "variant_b": sorted_v[1],
                "er_diff": round(er_diff, 2),
                "relative_diff_pct": round(relative_diff * 100, 1),
                "significant": significant,
            })

        return results

    def _get_experiment_start_date(self) -> date:
        """実験の開始基準日を取得"""
        # DBから最古の実験データを探す
        for experiment in EXPERIMENTS:
            data = self.db.get_experiment_results(experiment["name"])
            if data:
                try:
                    return date.fromisoformat(data[0]["thread_date"])
                except (ValueError, KeyError):
                    pass

        # データがなければ今日を開始日
        return date.today()

"""レポート生成: HTML ダッシュボード + 週次テキストレポート"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from config.settings import REPORTS_DIR, TARGET_FOLLOWERS, TARGET_IMPRESSIONS_3MO
from src.analytics.analyzer import EngagementAnalyzer
from src.analytics.engagement_db import EngagementDB

logger = logging.getLogger("xrunning.analytics.report")

JST = timezone(timedelta(hours=9))


class ReportGenerator:
    def __init__(self, db: EngagementDB):
        self.db = db
        self.analyzer = EngagementAnalyzer(db)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_weekly_text_report(self) -> str:
        """週次テキストレポートを生成"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = today

        growth = self.analyzer.get_growth_velocity()
        avg_er = self.analyzer.get_avg_engagement_rate(days=7)
        avg_views = self.analyzer.get_avg_views(days=7)
        topics = self.analyzer.get_best_topics(days=7)

        # フォロワー推移
        history = self.db.get_follower_history(days=14)
        follower_start = history[0]["follower_count"] if history else 0
        follower_end = growth["current_followers"]
        follower_diff = follower_end - follower_start

        # ベストトピック
        best_topic = topics[0]["topic"] if topics else "-"
        best_er = topics[0]["avg_er"] if topics else 0

        # 日次メトリクス
        daily = self.db.get_daily_metrics_range(days=7)
        best_day = max(daily, key=lambda d: d.get("total_views", 0)) if daily else None

        lines = [
            f"=== Xrunning 週次レポート ({week_start} ~ {week_end}) ===",
            "",
            f"フォロワー: {follower_start} -> {follower_end} ({'+' if follower_diff >= 0 else ''}{follower_diff})",
            f"平均日次ビュー: {avg_views:,.0f}",
            f"推定月間インプレッション: {growth['monthly_impressions']:,.0f}",
            f"平均エンゲージメント率: {avg_er:.2f}%",
            "",
        ]

        if best_day:
            lines.append(
                f"最高パフォーマンス: {best_day['thread_date']} "
                f"(views={best_day['total_views']:,}, ER={best_day['engagement_rate']:.2f}%)"
            )

        lines.append(f"ベストトピック: {best_topic} (ER={best_er:.2f}%)")
        lines.append("")

        # マイルストーン
        lines.append("--- マイルストーン ---")
        lines.append(
            f"500フォロワー: {growth['followers_pct']:.1f}% "
            f"({growth['current_followers']}/{TARGET_FOLLOWERS})"
        )
        if growth["est_days_to_500"]:
            lines.append(f"  到達予測: 約{growth['est_days_to_500']}日後")

        lines.append(
            f"5Mインプレッション/3ヶ月: {growth['impressions_pct']:.2f}% "
            f"({growth.get('impressions_3mo_current', 0):,.0f}/{TARGET_IMPRESSIONS_3MO:,})"
        )
        if growth["est_months_to_5m"]:
            lines.append(f"  到達予測: 約{growth['est_months_to_5m']:.0f}ヶ月後")

        lines.append("")
        lines.append("===")

        report = "\n".join(lines)

        # ファイルに保存
        report_path = REPORTS_DIR / f"weekly_{today}.txt"
        report_path.write_text(report, encoding="utf-8")

        # 週次サマリをDBに保存
        self.db.save_weekly_summary({
            "week_start": week_start.isoformat(),
            "avg_views": avg_views,
            "avg_likes": sum(d.get("total_likes", 0) for d in daily) / max(len(daily), 1),
            "avg_retweets": sum(d.get("total_retweets", 0) for d in daily) / max(len(daily), 1),
            "avg_engagement_rate": avg_er,
            "total_threads": len(daily),
            "best_topic": best_topic,
            "best_style": None,
            "follower_count_start": follower_start,
            "follower_count_end": follower_end,
            "estimated_monthly_impressions": growth["monthly_impressions"],
        })

        return report

    def generate_dashboard(self) -> Path:
        """HTML ダッシュボードを生成"""
        growth = self.analyzer.get_growth_velocity()
        avg_er = self.analyzer.get_avg_engagement_rate(days=30)
        daily_metrics = self.db.get_daily_metrics_range(days=30)
        topics = self.analyzer.get_best_topics(days=30)
        weekly = self.db.get_weekly_summaries(weeks=8)
        follower_history = self.db.get_follower_history(days=60)

        # チャート用データ
        dates_json = json.dumps([m["thread_date"] for m in reversed(daily_metrics)])
        views_json = json.dumps([m["total_views"] for m in reversed(daily_metrics)])
        er_json = json.dumps([round(m["engagement_rate"], 2) for m in reversed(daily_metrics)])
        likes_json = json.dumps([m["total_likes"] for m in reversed(daily_metrics)])

        topics_labels = json.dumps([t["topic"][:12] for t in topics[:10]])
        topics_er = json.dumps([round(t["avg_er"], 2) for t in topics[:10]])

        follower_dates = json.dumps([f["date"] for f in follower_history])
        follower_counts = json.dumps([f["follower_count"] for f in follower_history])

        # ベスト/ワーストスレッド
        best_threads = sorted(daily_metrics, key=lambda d: d.get("engagement_rate", 0), reverse=True)[:5]
        worst_threads = sorted(daily_metrics, key=lambda d: d.get("engagement_rate", 0))[:3]

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xrunning Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 28px; color: #38bdf8; }}
        .header p {{ color: #94a3b8; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
        .card h2 {{ font-size: 16px; color: #94a3b8; margin-bottom: 12px; }}
        .card .value {{ font-size: 32px; font-weight: bold; color: #f1f5f9; }}
        .card .sub {{ font-size: 14px; color: #64748b; margin-top: 4px; }}
        .progress-bar {{ background: #334155; border-radius: 8px; height: 12px; margin-top: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; border-radius: 8px; transition: width 0.5s; }}
        .progress-fill.blue {{ background: linear-gradient(90deg, #3b82f6, #38bdf8); }}
        .progress-fill.green {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
        .progress-fill.orange {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
        .chart-container {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
        .chart-container h2 {{ font-size: 16px; color: #94a3b8; margin-bottom: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-size: 13px; }}
        td {{ color: #e2e8f0; font-size: 14px; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
        .tag.good {{ background: #166534; color: #4ade80; }}
        .tag.bad {{ background: #7f1d1d; color: #fca5a5; }}
        .updated {{ text-align: center; color: #475569; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Xrunning Analytics Dashboard</h1>
        <p>@{growth.get('username', 'lumina_journal')} | AI News Curation</p>
    </div>

    <!-- マイルストーン -->
    <div class="grid">
        <div class="card">
            <h2>Followers</h2>
            <div class="value">{growth['current_followers']}<span style="font-size:16px;color:#64748b"> / {TARGET_FOLLOWERS}</span></div>
            <div class="progress-bar"><div class="progress-fill blue" style="width:{min(growth['followers_pct'], 100):.1f}%"></div></div>
            <div class="sub">{growth['followers_pct']:.1f}% | {'推定 ' + str(growth['est_days_to_500']) + '日後' if growth['est_days_to_500'] else '---'}</div>
        </div>
        <div class="card">
            <h2>Impressions (3-month)</h2>
            <div class="value">{growth.get('impressions_3mo_current', 0):,.0f}<span style="font-size:16px;color:#64748b"> / {TARGET_IMPRESSIONS_3MO:,}</span></div>
            <div class="progress-bar"><div class="progress-fill green" style="width:{min(growth['impressions_pct'], 100):.2f}%"></div></div>
            <div class="sub">{growth['impressions_pct']:.2f}% | {'推定 ' + str(int(growth['est_months_to_5m'])) + 'ヶ月後' if growth['est_months_to_5m'] else '---'}</div>
        </div>
        <div class="card">
            <h2>Avg Engagement Rate (30d)</h2>
            <div class="value">{avg_er:.2f}%</div>
            <div class="sub">Daily avg views: {self.analyzer.get_avg_views(7):,.0f}</div>
        </div>
        <div class="card">
            <h2>Monthly Impressions (est.)</h2>
            <div class="value">{growth['monthly_impressions']:,.0f}</div>
            <div class="sub">Follower growth: {growth['daily_follower_growth']:+.1f}/day</div>
        </div>
    </div>

    <!-- ビュー & ER トレンド -->
    <div class="chart-container">
        <h2>Daily Views & Engagement Rate (30d)</h2>
        <canvas id="trendChart" height="80"></canvas>
    </div>

    <div class="grid">
        <!-- トピック別 ER -->
        <div class="chart-container">
            <h2>Topic Performance (ER%)</h2>
            <canvas id="topicChart" height="120"></canvas>
        </div>

        <!-- フォロワー推移 -->
        <div class="chart-container">
            <h2>Follower Growth</h2>
            <canvas id="followerChart" height="120"></canvas>
        </div>
    </div>

    <!-- ベスト/ワーストスレッド -->
    <div class="chart-container">
        <h2>Best Performing Threads</h2>
        <table>
            <tr><th>Date</th><th>Views</th><th>Likes</th><th>RT</th><th>ER</th></tr>
            {''.join(f'<tr><td>{t["thread_date"]}</td><td>{t["total_views"]:,}</td><td>{t["total_likes"]}</td><td>{t["total_retweets"]}</td><td><span class="tag good">{t["engagement_rate"]:.2f}%</span></td></tr>' for t in best_threads)}
        </table>
    </div>

    <div class="updated">Last updated: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}</div>

    <script>
        // ビュー & ER トレンド
        new Chart(document.getElementById('trendChart'), {{
            type: 'line',
            data: {{
                labels: {dates_json},
                datasets: [
                    {{
                        label: 'Views',
                        data: {views_json},
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59,130,246,0.1)',
                        yAxisID: 'y',
                        tension: 0.3, fill: true,
                    }},
                    {{
                        label: 'ER%',
                        data: {er_json},
                        borderColor: '#f59e0b',
                        yAxisID: 'y1',
                        tension: 0.3, borderDash: [5,3],
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{ position: 'left', ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
                    y1: {{ position: 'right', ticks: {{ color: '#64748b' }}, grid: {{ display: false }} }},
                    x: {{ ticks: {{ color: '#64748b', maxRotation: 45 }}, grid: {{ color: '#1e293b' }} }}
                }},
                plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }}
            }}
        }});

        // トピック ER
        new Chart(document.getElementById('topicChart'), {{
            type: 'bar',
            data: {{
                labels: {topics_labels},
                datasets: [{{ label: 'Avg ER%', data: {topics_er}, backgroundColor: '#38bdf8' }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                scales: {{
                    x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}
                }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});

        // フォロワー推移
        new Chart(document.getElementById('followerChart'), {{
            type: 'line',
            data: {{
                labels: {follower_dates},
                datasets: [{{
                    label: 'Followers',
                    data: {follower_counts},
                    borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)',
                    tension: 0.3, fill: true,
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    x: {{ ticks: {{ color: '#64748b', maxRotation: 45 }}, grid: {{ color: '#1e293b' }} }},
                    y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }}
                }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});
    </script>
</body>
</html>"""

        output_path = REPORTS_DIR / "dashboard.html"
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"ダッシュボード生成: {output_path}")
        return output_path

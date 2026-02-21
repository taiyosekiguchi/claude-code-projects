# Xrunning 収益化戦略＋実装計画書

## Context

Xrunning は AI ニュースを自動収集・要約・X投稿する Python システム。現在は「投稿して終わり」の一方通行パイプライン。
フォロワー 0-100、X Premium 未加入、API Free プランの初期段階にある。

**目標**: X 広告収益シェア（要件: 500フォロワー + 5M impressions/3ヶ月）への到達
**課題**: 投稿後のエンゲージメント分析がゼロ。何が効果的か分からないまま投稿を続けている状態。

本計画は「投稿 → 分析 → 最適化 → 投稿」の自動フィードバックループを構築し、収益化到達までの最短経路を設計する。

---

## 1. 戦略概要

### 1.1 現状から収益化までのロードマップ

| フェーズ | 期間 | 目標 | 主な施策 |
|---------|------|------|---------|
| **Phase 1: 基盤構築** | Week 1-2 | 分析データの収集開始 | Playwright スクレイピング + SQLite DB |
| **Phase 2: 分析エンジン** | Week 3-4 | KPI 可視化・インサイト生成 | エンゲージメント分析 + ダッシュボード |
| **Phase 3: 自動最適化** | Week 5-6 | フィードバックループ稼働 | プロンプト動的最適化 + A/Bテスト |
| **Phase 4: 成長加速** | Week 7-8 | コンテンツ多様化 | 複数コンテンツタイプ + 戦略的ハッシュタグ |
| **マイルストーン: 500フォロワー** | 〜3-6ヶ月 | 広告収益シェア申請の前提条件 | 上記施策の継続的実行 |
| **マイルストーン: 5M imp/3ヶ月** | 〜6-12ヶ月 | 広告収益シェア開始 | X Premium加入 + 継続的最適化 |

### 1.2 収益化チャネル（段階的に展開）

| 優先度 | チャネル | 条件 | 想定収益 |
|--------|---------|------|---------|
| 1 | **X広告収益シェア** | X Premium + 500フォロワー + 5M imp/3ヶ月 | $50-400/月 |
| 2 | **アフィリエイト** | フォロワー増加後に導入 | $200-1,000/月 |
| 3 | **デジタル商品** | AI活用ガイド等の販売 | 変動 |
| 4 | **コンサルティング** | 権威性確立後 | $1,000+/案件 |

### 1.3 コアコンセプト: 自動フィードバックループ

```
投稿 → エンゲージメント収集 → 分析 → インサイト抽出
  ↑                                        ↓
  ← プロンプト最適化 ← スコア調整 ← 最適化指示
```

Free API ではエンゲージメント API が使えないため、**Playwright でツイートページを公開スクレイピング**して代替する。

---

## 2. 実装計画

### 2.1 アーキテクチャ

```
[既存パイプライン]                    [新規: 分析パイプライン]
08:00 実行                           09:00, 14:00, 07:50 実行

Collectors → Filter → Score → AI → Post    Scraper → DB → Analyzer
                ↑         ↑                              ↓
                |         |                     PromptOptimizer
                |         +---- topic_boosts ←── (トピック最適化)
                +------------ style_hints ←──── (スタイル最適化)
```

### 2.2 新規ファイル構成

```
src/analytics/           # 新規ディレクトリ
  __init__.py
  scraper.py             # Playwright ツイートメトリクス収集
  engagement_db.py       # SQLite データベースインターフェース
  analyzer.py            # KPI 計算・インサイト生成
  prompt_optimizer.py    # 動的プロンプト生成
  ab_testing.py          # A/B テストフレームワーク
  growth_strategy.py     # コンテンツ多様化・成長戦略
  report_generator.py    # ダッシュボード・レポート生成
  csv_importer.py        # X Analytics CSV インポート（バックアップ）
src/analytics_main.py    # 分析パイプラインオーケストレータ
scripts/run_analytics.sh # 分析実行スクリプト
launchd/com.taiyo.xrunning.analytics.plist  # 分析用スケジューラ
data/reports/            # レポート出力先
data/analytics_import/   # CSV インポート用
templates/dashboard.html # ダッシュボードテンプレート
```

### 2.3 既存ファイル修正

| ファイル | 修正内容 |
|---------|---------|
| `config/settings.py` | 分析設定、X_USERNAME、成長目標定数を追加 |
| `config/prompts.py` | コンテンツタイプ別プロンプトテンプレートを追加 |
| `src/processors/scorer.py` | `topic_boosts` パラメータを追加（エンゲージメントデータからのフィードバック） |
| `src/ai/summarizer.py` | `custom_prompt` パラメータを追加（動的プロンプト対応） |
| `src/main.py` | 分析フィードバックループを統合、`run_analytics()` 追加 |
| `.env.example` | `X_USERNAME=lumina_journal` を追加 |
| `requirements.txt` | `playwright>=1.40.0` を追加 |
| `scripts/setup.sh` | Playwright インストール手順を追加 |

---

## 3. コンポーネント詳細設計

### 3.1 エンゲージメント収集（Phase 1）

**方式**: Playwright ヘッドレスブラウザで公開ツイートページをスクレイピング

**ツイートURL**: `https://x.com/lumina_journal/status/{tweet_id}`
（tweet_id は既存の `data/posts/{date}.json` に保存済み）

**収集メトリクス**: views, likes, retweets, replies, quotes, bookmarks

**収集スケジュール**（投稿後のスナップショット）:
- T+1h (09:00): 初期エンゲージメント
- T+6h (14:00): ピーク時間帯
- T+24h (翌07:50): 成熟メトリクス
- T+48h (翌々07:50): ロングテール

**レート制限**: ツイート間15秒待機、1セッション最大10ページ、UA ローテーション

**フォールバック**: スクレイピング失敗時は X Analytics CSV 手動インポートで補完

### 3.2 データベース設計（Phase 1）

**ストレージ**: SQLite (`data/analytics.db`) — サーバー不要、Python 標準ライブラリ対応

**主要テーブル**:

```sql
-- メトリクスのスナップショット（不変ログ）
metric_snapshots:
  tweet_id, thread_date, position_in_thread,
  snapshot_type ('1h'|'6h'|'24h'|'48h'),
  views, likes, retweets, replies, quotes, bookmarks, scraped_at

-- 日次スレッドパフォーマンス集約
daily_thread_metrics:
  thread_date, total_views, total_likes, total_retweets,
  engagement_rate, top_tweet_position, content_style(JSON), topics_covered(JSON)

-- トピック別パフォーマンス
topic_performance:
  topic, thread_date, tweet_position, views, likes, engagement_rate

-- A/B テスト記録
style_experiments:
  thread_date, variant_name, variant_params(JSON), engagement_rate, views

-- フォロワー推移
follower_log:
  date, follower_count, following_count, source
```

### 3.3 分析エンジン（Phase 2）

**`analyzer.py`** が算出する KPI:

| KPI | 計算式 | 用途 |
|-----|--------|------|
| エンゲージメント率 | (likes+RT+replies+quotes) / views | コンテンツ品質指標 |
| トピック別エンゲージメント | トピックごとの平均 ER | スコアリング最適化 |
| ハッシュタグ効果 | ハッシュタグ有無別 ER 比較 | ハッシュタグ戦略 |
| スレッド内ポジション効果 | ポジション別の平均 likes | 構成最適化 |
| 成長速度 | フォロワー増加率/日 | マイルストーン予測 |
| 月間インプレッション推定 | 直近7日平均 × 30 | 5M到達予測 |

**最小データ閾値**: 14日分のデータが溜まるまではフィードバックループを起動しない

### 3.4 自動最適化ループ（Phase 3）

#### プロンプト動的最適化 (`prompt_optimizer.py`)

既存の `SUMMARIZE_PROMPT` に以下を動的に追記:

```
## パフォーマンスデータに基づく最適化指示（自動生成）

### 高エンゲージメントトピック（優先）
- Claude / Anthropic 関連（平均 ER: 4.2%）
- AI エージェント関連（平均 ER: 3.8%）

### スタイル指示
- 1ツイート目に絵文字を2個使用する（ER +23%）
- 最後のツイートは質問形式にする（リプライ率 +40%）

### 今回の実験
【A/Bテスト: question_cta】最後のツイートを質問で締める
```

#### スコアリング最適化 (`scorer.py` 修正)

`score_articles()` に `topic_boosts` パラメータを追加:
- エンゲージメントが高いトピックの記事に最大 1.5x ブースト
- エンゲージメントが低いトピックは最小 0.7x に抑制
- 直近30日のデータに基づいて自動計算

#### A/B テスト (`ab_testing.py`)

1日1投稿なので、**7日間ずつ2バリアントを交互に実行** して比較:

| テスト | バリアント A | バリアント B | 期間 |
|--------|------------|------------|------|
| 絵文字量 | 各ツイート2-3個 | 1ツイート目のみ1個 | 14日 |
| CTA スタイル | 質問で締める | いいね・RTを呼びかけ | 14日 |
| イントロ | 挨拶＋ハイライト | 衝撃的ニュースから開始 | 14日 |

**注意**: 1日1投稿ではサンプルサイズが小さいため、50%以上の差がある場合のみ有意と判断。方向性の参考指標として活用。

### 3.5 成長戦略（Phase 4）

#### コンテンツタイプの多様化

| 曜日 | コンテンツタイプ | 説明 |
|------|----------------|------|
| 月-金 | `news_thread` | 通常の AI ニューススレッド（現行） |
| 土 | `weekly_roundup` | 今週のトップニュースまとめ |
| 日 | `tool_spotlight` / `tips_thread` | AI ツール紹介 or AI活用Tips（隔週交互） |

各コンテンツタイプ用のプロンプトテンプレートを `config/prompts.py` に追加。

#### ハッシュタグ戦略

```python
HASHTAG_POOLS = {
    "always": ["#AIニュース", "#AI"],
    "rotate_ja": ["#生成AI", "#Claude", "#ChatGPT", "#機械学習", "#AIエージェント"],
    "rotate_en": ["#ArtificialIntelligence", "#GenerativeAI"],
}
```

エンゲージメントデータに基づいて効果の高いハッシュタグを自動選択。

### 3.6 ダッシュボード・レポート（Phase 2-4）

**HTMLダッシュボード** (`data/reports/dashboard.html`):
- フォロワー進捗バー（現在値 / 500 目標）
- インプレッション進捗バー（現在値 / 5,000,000 目標）
- 各マイルストーンへの推定日数
- 週次エンゲージメント率トレンド（Chart.js 折れ線グラフ）
- トピック別パフォーマンス（棒グラフ）
- A/B テスト結果
- ベスト/ワーストスレッド一覧

**週次テキストレポート** (日曜07:50に自動生成、ログ出力):
```
=== Xrunning 週次レポート ===
フォロワー: 45 → 52 (+7, +15.6%)
推定月間インプレッション: 12,500
平均エンゲージメント率: 3.2%
500フォロワー到達予測: 約64日後
===
```

---

## 4. スケジューリング設計

### 既存 launchd（変更なし）

| 時刻 | 処理 | plist |
|------|------|-------|
| 08:00 | フルパイプライン実行 | `com.taiyo.xrunning.plist` |
| 12:00 | 投稿失敗リトライ | 同上 |
| 20:00 | 最終リトライ | 同上 |

### 新規 launchd

| 時刻 | 処理 | plist |
|------|------|-------|
| 07:50 | T+24h/48h スナップショット + 週次レポート(日曜) | `com.taiyo.xrunning.analytics.plist` |
| 09:00 | T+1h スナップショット | 同上 |
| 14:00 | T+6h スナップショット | 同上 |

---

## 5. リスクと対策

| リスク | 影響度 | 対策 |
|--------|--------|------|
| X の HTML 構造変更でスクレイパー破損 | 高 | 複数セレクタ戦略 + CSV インポートのフォールバック + セレクタを設定ファイル化 |
| スクレイピングがブロック/レート制限される | 中 | 1日20-30リクエストに制限 + UA ローテーション + 公開ページのみアクセス |
| 1日1投稿ではデータ不足で分析精度が低い | 高 | スレッド内の各ツイート（5件/日）を個別分析 + 14日以上のデータで判断 + ベイズ信頼区間使用 |
| A/B テストが統計的に弱い | 高 | 14日/バリアント + 大きな差（50%以上）のみ有意判断 + 方向性指標として活用 |
| Playwright の launchd 環境での動作 | 中 | ヘッドレスモード + 環境変数設定 + `--skip-scrape` フラグで graceful degradation |
| プロンプト肥大化によるコスト増 | 低 | 動的追記は200語以内に制限 + sonnet モデル維持 |

---

## 6. 実装優先順位

### Week 1-2: Phase 1 — データ収集基盤（最優先）
1. `src/analytics/engagement_db.py` — SQLite スキーマ + CRUD
2. `src/analytics/scraper.py` — Playwright スクレイパー
3. `src/analytics_main.py` — 分析パイプラインオーケストレータ
4. `launchd/com.taiyo.xrunning.analytics.plist` — スケジューラ
5. `config/settings.py` — 分析設定追加（`X_USERNAME` 等）
6. `requirements.txt` + `setup.sh` — Playwright 追加

### Week 3-4: Phase 2 — 分析エンジン
7. `src/analytics/analyzer.py` — KPI 計算・インサイト
8. `src/analytics/csv_importer.py` — CSV インポート
9. `src/analytics/report_generator.py` — ダッシュボード + 週次レポート
10. `templates/dashboard.html` — HTML テンプレート

### Week 5-6: Phase 3 — 自動最適化ループ
11. `src/analytics/prompt_optimizer.py` — 動的プロンプト生成
12. `src/analytics/ab_testing.py` — A/B テストフレームワーク
13. `src/processors/scorer.py` 修正 — topic_boosts 統合
14. `src/ai/summarizer.py` 修正 — custom_prompt 対応
15. `src/main.py` 修正 — フィードバックループ統合

### Week 7-8: Phase 4 — 成長加速
16. `src/analytics/growth_strategy.py` — コンテンツ多様化
17. `config/prompts.py` 拡張 — コンテンツタイプ別テンプレート

---

## 7. 検証方法

### Phase 1 完了時
- `python src/analytics_main.py --test` で直近の投稿ツイートのスクレイピングが成功すること
- `data/analytics.db` にスナップショットが記録されること
- launchd で 09:00/14:00/07:50 に自動実行されること

### Phase 2 完了時
- `python src/analytics_main.py --report` でダッシュボード HTML が生成されること
- ダッシュボードにエンゲージメント率・トピック別パフォーマンスが表示されること

### Phase 3 完了時
- 朝の投稿パイプラインで、過去データに基づいた動的プロンプトが生成されること
- ログに「最適化ヒント適用: {hints}」が出力されること
- A/B テストバリアントがスケジュール通り切り替わること

### Phase 4 完了時
- 土曜に weekly_roundup、日曜に tool_spotlight/tips が自動で生成されること
- コンテンツタイプごとのエンゲージメント比較がダッシュボードに表示されること

### 全体通し検証
1. `bash scripts/setup.sh` で環境構築が完了すること
2. `bash scripts/run.sh --dry-run` でフルパイプライン（分析込み）が動作すること
3. 2週間運用後、ダッシュボードにトレンドデータが蓄積されていること
4. プロンプト最適化が投稿内容に反映されていること（ログで確認）

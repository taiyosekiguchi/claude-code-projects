"""Claude CLI連携によるAI要約生成"""

import asyncio
import json
import logging
import subprocess
from dataclasses import asdict

from config.prompts import SUMMARIZE_PROMPT
from config.settings import CLAUDE_MAX_RETRIES, CLAUDE_RETRY_INTERVAL, CLAUDE_TIMEOUT
from src.models.article import Article

logger = logging.getLogger("xrunning.summarizer")


def generate_thread(articles: list[Article]) -> list[str]:
    """
    Claude Code CLIで記事をスレッド形式に要約する。
    失敗時はリトライし、全て失敗した場合はNoneを返す。
    """
    articles_json = json.dumps(
        [a.to_dict() for a in articles],
        ensure_ascii=False,
        indent=2,
    )
    prompt = SUMMARIZE_PROMPT.format(articles_json=articles_json)

    for attempt in range(1, CLAUDE_MAX_RETRIES + 1):
        try:
            logger.info(f"Claude CLI実行中 (試行{attempt}/{CLAUDE_MAX_RETRIES})...")
            result = subprocess.run(
                ["claude", "-p", "--model", "sonnet"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT,
            )

            if result.returncode != 0:
                error_detail = result.stderr[:200] or result.stdout[:200]
                logger.error(f"Claude CLI終了コード {result.returncode}: {error_detail}")
                raise RuntimeError(f"Claude CLI error: {error_detail}")

            output = result.stdout.strip()
            if not output:
                raise RuntimeError("Claude CLIの出力が空です")

            tweets = _parse_thread(output)
            if tweets:
                logger.info(f"スレッド生成成功: {len(tweets)}ツイート")
                return tweets
            else:
                raise RuntimeError("ツイートのパースに失敗しました")

        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLIタイムアウト ({CLAUDE_TIMEOUT}秒)")
        except Exception as e:
            logger.error(f"Claude CLI失敗 (試行{attempt}): {e}")

        if attempt < CLAUDE_MAX_RETRIES:
            logger.info(f"{CLAUDE_RETRY_INTERVAL}秒後にリトライ...")
            import time
            time.sleep(CLAUDE_RETRY_INTERVAL)

    logger.error("Claude CLIが全てのリトライで失敗")
    return []


def _parse_thread(output: str) -> list[str]:
    """Claude CLIの出力を"---"区切りでツイートリストに変換する"""
    tweets = []
    for part in output.split("---"):
        text = part.strip()
        if text:
            tweets.append(text)
    return tweets


def build_fallback_thread(articles: list[Article]) -> list[str]:
    """Claude CLIが使えない場合の簡易スレッド生成"""
    tweets = ["おはようございます！本日のAIニュースです\n\n#AIニュース #AI"]

    for i, article in enumerate(articles[:5], 1):
        title = article.title[:100]
        tweet = f"【{i}】{title}\n{article.url}"
        tweets.append(tweet)

    tweets.append(
        "以上、本日のAIニュースでした！\n\n"
        "気になるニュースがあればいいね・リポストお願いします\n"
        "#AI #AIニュース #Claude"
    )
    return tweets

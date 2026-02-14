#!/usr/bin/env python3
"""
Daily Insight Generator CLI

用法:
    python -m src.insight.cli [--date YYYY-MM-DD] [--format markdown|json|both]

示例:
    python -m src.insight.cli
    python -m src.insight.cli --date 2026-02-14
    python -m src.insight.cli --format markdown
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime

from ..core.config import load_config
from .daily_insight_generator import DailyInsightGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="生成每日技术洞察报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python -m src.insight.cli                           # 生成今日报告
    python -m src.insight.cli --date 2026-02-14         # 生成指定日期报告
    python -m src.insight.cli --format markdown         # 只输出 Markdown
    python -m src.insight.cli --preview                 # 预览模式，只打印不保存
        """,
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="目标日期 (YYYY-MM-DD 格式)，默认为今天",
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "json", "both"],
        default="both",
        help="输出格式 (默认: both)",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (默认: config/config.yaml)",
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="预览模式，只打印到终端不保存文件",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出",
    )

    return parser.parse_args()


async def main() -> int:
    """主函数"""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 解析日期
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
            return 1
    else:
        target_date = date.today()

    logger.info(f"Generating daily insight for {target_date}")

    # 加载配置
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return 1

    # 创建生成器
    generator = DailyInsightGenerator(config)

    try:
        if args.preview:
            # 预览模式
            summaries = await generator.load_summaries(target_date)
            if not summaries:
                logger.warning(f"No summaries found for {target_date}")
                return 1

            logger.info(f"Found {len(summaries)} summaries")
            insight = await generator.generate_insight(summaries, target_date)

            # 打印 Markdown 到终端
            print("\n" + "=" * 80)
            print(insight.to_markdown())
            print("=" * 80 + "\n")

        else:
            # 正常模式，生成并保存
            insight, output_path = await generator.generate_and_save(
                target_date=target_date,
                output_format=args.format,
            )

            logger.info(f"✅ Daily insight generated successfully!")
            logger.info(f"📁 Output: {output_path}")

            # 打印简要统计
            print("\n📊 统计摘要:")
            print(f"   - 分析条目: {insight.statistics.total_analyzed}")
            print(f"   - 筛除条目: {insight.statistics.filtered_out_count}")
            print(f"   - 核心推荐: {len(insight.high_impact_picks)} 个")
            print(f"   - 遗珠发现: {len(insight.hidden_gems)} 个")
            print(f"   - 来源分布: {insight.statistics.sources_breakdown}")
            print()

        return 0

    except Exception as e:
        logger.error(f"Failed to generate insight: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    finally:
        await generator.close()


def run():
    """入口函数"""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()


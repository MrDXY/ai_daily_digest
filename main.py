#!/usr/bin/env python3
"""
AI 内容脱水日报 - 主入口

Usage:
    python main.py                    # 使用默认配置运行
    python main.py --config path.yaml # 使用指定配置
    python main.py --provider claude  # 指定 AI provider
    python main.py --dry-run          # 试运行（不调用 AI）
"""

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from notifier.readme_updater import update_readme, ReadmeUpdater

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import load_config, AppConfig, get_report_date_dir, get_cache_dir
from src.core.models import FetchTask, FetchResult, FetchStatus, Article, DigestReport
from src.core.exceptions import DigestException
from src.crawler import FetchManager
from src.processor import ProcessingPipeline, HTMLCleaner
from src.notifier import ReportGenerator, TerminalDisplay
from src.generator import ConfigGenerator


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


class DailyDigestApp:
    """
    日报生成应用

    编排整个处理流程：
    1. 加载配置
    2. 创建抓取任务
    3. 执行抓取
    4. 处理和摘要
    5. 生成报告
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        provider: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.config_path = config_path
        self.provider_override = provider
        self.dry_run = dry_run

        self.config: Optional[AppConfig] = None
        self.display = TerminalDisplay()
        self.updater = ReadmeUpdater(readme_path="README.md", report_dir="output/report")

    async def run(self) -> DigestReport:
        """运行完整的日报生成流程"""
        start_time = time.time()

        # 显示启动横幅
        self.display.show_banner()

        # 加载配置
        self.config = load_config(self.config_path)

        # 重新初始化显示器（使用配置中的评分阈值）
        self.display = TerminalDisplay(
            score_threshold=float(self.config.digest.score_threshold),
            show_low_score=self.config.output.terminal.get("show_low_score", False),
        )

        # 覆盖 AI provider
        if self.provider_override:
            self.config.ai.default_provider = self.provider_override

        # 显示配置
        self._show_config_summary()

        # 创建任务
        tasks = self._create_fetch_tasks()
        logger.info(f"Created {len(tasks)} fetch tasks")

        if not tasks:
            self.display.show_warning("No tasks to process")
            return DigestReport(date=datetime.now().strftime("%Y-%m-%d"))

        # 使用 FetchManager 进行抓取和处理（保持 manager 可用于二次爬取）
        errors: list[str] = []

        async with FetchManager(
            self.config.crawler,
        ) as fetch_manager:
            # 执行抓取
            self.display.show_info("Starting fetch...")
            results = await self._execute_fetch_with_manager(tasks, fetch_manager)

            # 统计抓取结果
            success_count = sum(1 for r in results if r.status == FetchStatus.SUCCESS)
            failed_count = len(results) - success_count
            self.display.show_fetch_result(success_count, failed_count, len(results))

            # 记录抓取失败
            errors.extend(self._collect_fetch_errors(results))

            # 处理和摘要
            if self.dry_run:
                self.display.show_info("Dry run mode - skipping AI processing")
                articles = self._create_mock_articles(results)
            else:
                self.display.show_info("Processing and summarizing...")
                articles, pipeline_errors = await self._process_results(results, fetch_manager)
                errors.extend(pipeline_errors)

        # 生成报告
        self.display.show_info("Generating report...")
        processing_time = time.time() - start_time

        generator = ReportGenerator(self.config)
        report = await generator.generate(
            articles=articles,
            total_fetched=len(tasks),
            errors=errors,
            processing_time=processing_time,
        )

        # 显示高质量项目（使用去重后的报告结果）
        self.display.show_high_quality_articles(report.articles)

        # 显示摘要
        self.display.show_report_summary(report)

        # 显示完成信息
        report_dir = get_report_date_dir(self.config, report.date)
        report_path = report_dir / self.config.output.report_filename.format(
            date=report.date
        )
        self.display.show_completion(str(report_path))

        print("正在更新 README 索引...")
        self.updater.update()

        return report

    def _show_config_summary(self) -> None:
        """显示配置摘要"""
        enabled_sites = [s.name for s in self.config.sites if s.enabled]

        summary = {
            "AI Provider": self.config.ai.default_provider,
            "Sites": ", ".join(enabled_sites),
            "Concurrency": self.config.crawler.concurrency,
            "Score Threshold": self.config.digest.score_threshold,
            "Dry Run": self.dry_run,
        }

        self.display.show_config(summary)

    def _create_fetch_tasks(self) -> list[FetchTask]:
        """创建抓取任务"""
        tasks = []

        for site_ref in self.config.sites:
            if not site_ref.enabled:
                continue

            site_config = self.config.site_configs.get(site_ref.name, {})
            if not site_config:
                logger.warning(f"No config found for site: {site_ref.name}")
                continue

            site_url = site_config.get("site", {}).get("url")
            if not site_url:
                logger.warning(f"No URL found for site: {site_ref.name}")
                continue

            task = FetchTask(
                id=f"{site_ref.name}_{uuid.uuid4().hex[:8]}",
                url=site_url,
                site_name=site_ref.name,
                site_config=site_config,
            )
            tasks.append(task)

        return tasks

    async def _execute_fetch_with_manager(
        self,
        tasks: list[FetchTask],
        manager: 'FetchManager',
    ) -> list[FetchResult]:
        """使用指定的 FetchManager 执行抓取"""
        # 使用进度条
        progress = self.display.create_progress()

        with progress:
            task_id = progress.add_task(
                "Fetching...",
                total=len(tasks),
            )

            results = []
            for task in tasks:
                result = await manager.fetch(task)
                results.append(result)
                progress.update(task_id, advance=1)

        return results

    async def _execute_fetch(self, tasks: list[FetchTask]) -> list[FetchResult]:
        """执行抓取（独立使用 FetchManager）"""
        # 获取缓存配置
        cache_dir = get_cache_dir(self.config)
        cache_enabled = self.config.crawler.cache.enabled

        async with FetchManager(
            self.config.crawler,
            cache_dir=cache_dir,
            cache_enabled=cache_enabled,
        ) as manager:
            # 清理旧缓存
            keep_days = self.config.crawler.cache.keep_days
            manager.clear_old_cache(keep_days)

            results = await self._execute_fetch_with_manager(tasks, manager)

            # 显示缓存统计
            cache_stats = manager.get_stats().get("cache", {})
            if cache_stats.get("enabled"):
                self.display.show_info(
                    f"Cache: {cache_stats.get('total_files', 0)} files, "
                    f"{cache_stats.get('total_size_mb', 0)} MB"
                )

        return results

    async def _process_results(
        self,
        results: list[FetchResult],
        fetch_manager: Optional['FetchManager'] = None,
    ) -> tuple[list[Article], list[str]]:
        """处理抓取结果"""
        articles = []
        errors: list[str] = []

        async with ProcessingPipeline(self.config) as pipeline:
            # 设置二次爬取回调（如果有 fetch_manager）
            if fetch_manager:
                async def fetch_details_callback(urls: list[str], site_config: dict) -> list[FetchResult]:
                    """二次爬取详情页的回调函数"""
                    detail_tasks = []
                    for url in urls:
                        task = FetchTask(
                            id=f"detail_{uuid.uuid4().hex[:8]}",
                            url=url,
                            site_name="detail",
                            site_config=site_config,
                        )
                        detail_tasks.append(task)

                    return await fetch_manager.fetch_many(detail_tasks)

                pipeline.set_fetch_callback(fetch_details_callback)

            progress = self.display.create_progress()

            with progress:
                task_id = progress.add_task(
                    "Processing...",
                    total=len(results),
                )

                for result in results:
                    if result.status != FetchStatus.SUCCESS:
                        progress.update(task_id, advance=1)
                        continue

                    # 查找对应的站点配置
                    site_config = {}
                    for site_ref in self.config.sites:
                        if site_ref.name in result.task_id:
                            site_config = self.config.site_configs.get(
                                site_ref.name, {}
                            )
                            break

                    try:
                        site_articles = await pipeline.process(result, site_config)
                        articles.extend(site_articles)
                    except Exception as e:
                        logger.error(f"Processing error: {e}")

                    progress.update(task_id, advance=1)

            errors.extend(pipeline.get_errors())

        return articles, errors

    def _collect_fetch_errors(self, results: list[FetchResult]) -> list[str]:
        """收集抓取失败错误信息"""
        errors: list[str] = []
        for result in results:
            if result.status == FetchStatus.SUCCESS:
                continue

            status_code = result.status_code or "N/A"
            error_message = result.error_message or "Unknown error"
            errors.append(
                f"抓取失败: {result.url} | HTTP {status_code} | {error_message}"
            )

        return errors

    def _create_mock_articles(
        self,
        results: list[FetchResult],
    ) -> list[Article]:
        """创建模拟文章（用于 dry-run 模式）"""
        articles = []
        cleaner = HTMLCleaner()

        for result in results:
            if result.status != FetchStatus.SUCCESS or not result.html:
                continue

            # 查找站点配置
            site_config = {}
            site_name = "Unknown"
            for site_ref in self.config.sites:
                if site_ref.name in result.task_id:
                    site_config = self.config.site_configs.get(site_ref.name, {})
                    site_name = site_config.get("site", {}).get("name", site_ref.name)
                    break

            # 提取基本信息
            parser_config = site_config.get("list_parser", {})
            container = parser_config.get("container")
            selectors = parser_config.get("selectors", {})
            url_prefix = parser_config.get("url_prefix", "")

            if container and selectors:
                # 过滤掉无效的 CSS 选择器（如相邻兄弟选择器 "+ tr"）
                valid_selectors = {
                    k: v for k, v in selectors.items()
                    if v and not v.strip().startswith('+')
                }
                items = cleaner.extract_structured(
                    html=result.html,
                    selectors=valid_selectors,
                    container_selector=container,
                    base_url=result.url,
                    url_prefix=url_prefix,
                )

                for i, item in enumerate(items[:10]):  # 限制数量
                    article = Article(
                        id=f"mock_{uuid.uuid4().hex[:8]}",
                        source=site_name,
                        url=item.get("url", result.url),
                        title=item.get("title", f"Mock Article {i+1}"),
                        description=item.get("description"),
                        summary="[Dry Run] 这是模拟摘要，实际运行时会调用 AI 生成。",
                        core_value="[Dry Run] 模拟核心价值",
                        tech_stack=["Python", "Mock"],
                        recommendation="[Dry Run] 模拟推荐理由",
                        score=50.0 + (i % 5) * 10,  # 模拟 50-90 分
                        language=item.get("language"),
                    )
                    articles.append(article)

        return articles


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="AI 内容脱水日报生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c", "--config",
        type=str,
        help="配置文件路径 (默认: config/config.yaml)",
    )

    parser.add_argument(
        "-p", "--provider",
        type=str,
        choices=["claude", "openai", "azure_openai", "custom"],
        help="指定 AI provider",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式（不调用 AI）",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出",
    )

    # 配置生成相关参数
    parser.add_argument(
        "--generate-config",
        type=str,
        metavar="URL",
        help="根据指定 URL 生成站点配置文件",
    )

    parser.add_argument(
        "--use-js",
        action="store_true",
        help="生成配置时使用 JS 渲染（配合 --generate-config 使用）",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="配置文件输出路径（配合 --generate-config 使用）",
    )

    return parser.parse_args()


async def main() -> int:
    """主函数"""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # 如果是生成配置模式
        if args.generate_config:
            return await generate_site_config(
                url=args.generate_config,
                config_path=args.config,
                provider=args.provider,
                use_js=args.use_js,
                output_path=args.output,
            )

        # 正常的日报生成模式
        app = DailyDigestApp(
            config_path=args.config,
            provider=args.provider,
            dry_run=args.dry_run,
        )

        report = await app.run()

        return 0 if report.total_processed > 0 else 1

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 130

    except DigestException as e:
        logger.error(f"Application error: {e}")
        return 1

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


async def generate_site_config(
    url: str,
    config_path: Optional[str] = None,
    provider: Optional[str] = None,
    use_js: bool = False,
    output_path: Optional[str] = None,
) -> int:
    """
    生成站点配置文件

    Args:
        url: 目标 URL
        config_path: 主配置文件路径
        provider: AI provider
        use_js: 是否使用 JS 渲染
        output_path: 输出路径

    Returns:
        退出码
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    console = Console()

    console.print(Panel.fit(
        f"[bold blue]🔧 站点配置生成器[/bold blue]\n\n"
        f"目标 URL: [cyan]{url}[/cyan]\n"
        f"JS 渲染: [yellow]{'是' if use_js else '否'}[/yellow]",
        border_style="blue",
    ))

    # 加载配置
    config = load_config(config_path)

    # 覆盖 AI provider
    if provider:
        config.ai.default_provider = provider

    console.print(f"\n[dim]AI Provider: {config.ai.default_provider}[/dim]\n")

    # 创建生成器
    generator = ConfigGenerator(config)

    try:
        with console.status("[bold green]正在处理...", spinner="dots"):
            config_file_path, config_content = await generator.generate_config(
                url=url,
                use_js=use_js,
                output_path=output_path,
            )

        # 显示生成的配置
        console.print("\n[bold green]✅ 配置生成成功！[/bold green]\n")
        console.print(f"配置文件已保存到: [cyan]{config_file_path}[/cyan]\n")

        # 显示配置内容预览
        console.print("[bold]生成的配置内容:[/bold]\n")
        syntax = Syntax(config_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)

        # 提示后续操作
        console.print("\n[dim]提示: 请检查生成的配置文件，并根据需要进行调整。[/dim]")
        console.print("[dim]然后将其添加到 config/config.yaml 的 sites 列表中即可使用。[/dim]")

        return 0

    except Exception as e:
        console.print(f"\n[bold red]❌ 配置生成失败: {e}[/bold red]")
        logger.exception("配置生成错误")
        return 1

    finally:
        await generator.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

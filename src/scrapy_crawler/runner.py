"""
Scrapy 爬虫运行器
提供与现有系统集成的接口
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from ..core.models import FetchResult, FetchStatus, FetchMethod, FetchPageType, FetchTask
from ..core.config import CrawlerConfig


logger = logging.getLogger(__name__)


class ScrapyCrawlerRunner:
    """
    Scrapy 爬虫运行器

    提供与现有 FetchManager 兼容的接口
    """

    def __init__(
        self,
        config: CrawlerConfig,
        cache_dir: Optional[Path] = None,
        cache_enabled: bool = True,
    ):
        self.config = config
        self.cache_dir = cache_dir
        self.cache_enabled = cache_enabled

        self._results: list[FetchResult] = []
        self._articles: list[dict[str, Any]] = []
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """关闭资源"""
        pass

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "requests": self._request_count,
            "success": self._success_count,
            "failure": self._failure_count,
        }

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行单个抓取任务

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        site_config = task.site_config

        # 使用同步方式运行 Scrapy
        result = await self._run_spider_async(site_config, task)

        self._request_count += 1
        if result.status == FetchStatus.SUCCESS:
            self._success_count += 1
        else:
            self._failure_count += 1

        return result

    async def fetch_all(self, tasks: list[FetchTask]) -> list[FetchResult]:
        """
        执行多个抓取任务

        Args:
            tasks: 抓取任务列表

        Returns:
            list[FetchResult]: 抓取结果列表
        """
        results = []

        # 按站点分组
        site_tasks: dict[str, list[FetchTask]] = {}
        for task in tasks:
            site_name = task.site_name
            if site_name not in site_tasks:
                site_tasks[site_name] = []
            site_tasks[site_name].append(task)

        # 为每个站点运行 Spider
        for site_name, site_task_list in site_tasks.items():
            if not site_task_list:
                continue

            task = site_task_list[0]
            site_config = task.site_config

            logger.info(f"Running spider for {site_name}...")

            try:
                spider_results, articles = await self._run_spider_for_site(
                    site_config, site_name
                )

                for spider_result in spider_results:
                    result = self._convert_to_fetch_result(spider_result, task)
                    results.append(result)
                    self._results.append(result)

                self._articles.extend(articles)

            except Exception as e:
                logger.error(f"Spider failed for {site_name}: {e}")
                for t in site_task_list:
                    result = FetchResult(
                        task_id=t.id,
                        url=t.url,
                        status=FetchStatus.FAILED,
                        method=FetchMethod.UNKNOWN,
                        error_message=str(e),
                    )
                    results.append(result)

        return results

    async def _run_spider_async(
        self, site_config: dict[str, Any], task: FetchTask
    ) -> FetchResult:
        """异步运行 Spider"""
        spider_results, articles = await self._run_spider_for_site(
            site_config, task.site_name
        )

        if spider_results:
            return self._convert_to_fetch_result(spider_results[0], task)

        return FetchResult(
            task_id=task.id,
            url=task.url,
            status=FetchStatus.FAILED,
            method=FetchMethod.UNKNOWN,
            error_message="No results from spider",
        )

    async def _run_spider_for_site(
        self, site_config: dict[str, Any], site_name: str
    ) -> tuple[list[dict], list[dict]]:
        """
        为特定站点运行 Spider

        使用 asyncio 运行 Scrapy
        """
        # 获取设置
        settings = self._get_scrapy_settings()

        results = []
        articles = []

        def run_spider():
            nonlocal results, articles
            # 延迟导入，避免顶层导入问题
            from scrapy.crawler import CrawlerProcess
            from scrapy import signals
            from .spiders.site_spider import SiteSpider

            process = CrawlerProcess(settings)

            def spider_closed(spider, reason):
                nonlocal results, articles
                results = list(getattr(spider, 'results', []))
                articles = list(getattr(spider, 'articles', []))

            crawler = process.create_crawler(SiteSpider)
            crawler.signals.connect(spider_closed, signal=signals.spider_closed)

            process.crawl(crawler, site_config=site_config, site_name=site_name)
            process.start()

        # 在线程中运行 Scrapy
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_spider)

        return results, articles

    def _get_scrapy_settings(self) -> dict[str, Any]:
        """获取 Scrapy 设置"""
        return {
            "BOT_NAME": "ai_daily_digest",
            "SPIDER_MODULES": ["src.scrapy_crawler.spiders"],
            "NEWSPIDER_MODULE": "src.scrapy_crawler.spiders",
            "ROBOTSTXT_OBEY": False,
            "CONCURRENT_REQUESTS": self.config.concurrency,
            "DOWNLOAD_DELAY": 1,
            "RANDOMIZE_DOWNLOAD_DELAY": True,
            "COOKIES_ENABLED": True,
            "DOWNLOAD_TIMEOUT": self.config.timeout,
            "RETRY_ENABLED": True,
            "RETRY_TIMES": self.config.max_retries,
            "LOG_LEVEL": "WARNING",
            "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
            "DOWNLOADER_MIDDLEWARES": {
                "src.scrapy_crawler.middlewares.RandomUserAgentMiddleware": 400,
                "src.scrapy_crawler.middlewares.StealthMiddleware": 450,
            },
            "ITEM_PIPELINES": {},
        }

    def _convert_to_fetch_result(
        self, spider_result: dict[str, Any], task: FetchTask
    ) -> FetchResult:
        """将 Spider 结果转换为 FetchResult"""
        status = spider_result.get("status", "failed")

        return FetchResult(
            task_id=task.id,
            url=spider_result.get("url", task.url),
            status=FetchStatus.SUCCESS if status == "success" else FetchStatus.FAILED,
            method=FetchMethod.CRAWL4AI,
            page_type=FetchPageType.LIST if spider_result.get("page_type") == "list" else FetchPageType.CONTENT,
            html=spider_result.get("html"),
            text=spider_result.get("text"),
            title=spider_result.get("title"),
            description=spider_result.get("description"),
            parsed_data=spider_result.get("parsed_data", {}),
            status_code=spider_result.get("status_code"),
            error_message=spider_result.get("error_message"),
        )

    def get_articles(self) -> list[dict[str, Any]]:
        """获取所有抓取的文章"""
        return self._articles


def load_site_configs(config_dir: str = "config/sites") -> list[dict[str, Any]]:
    """
    加载所有站点配置

    Args:
        config_dir: 配置目录路径

    Returns:
        list: 站点配置列表
    """
    configs = []
    config_path = Path(config_dir)

    if not config_path.exists():
        logger.warning(f"Config directory not found: {config_dir}")
        return configs

    for yaml_file in config_path.glob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if config:
                    configs.append(config)
                    logger.info(f"Loaded config: {yaml_file.name}")
        except Exception as e:
            logger.error(f"Failed to load {yaml_file}: {e}")

    return configs

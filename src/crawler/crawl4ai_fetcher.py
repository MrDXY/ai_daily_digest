"""
Crawl4AI 抓取器
使用 Crawl4AI 获取页面内容
"""

import importlib
import logging
import time
from typing import Any, Optional

from ..core.models import FetchTask, FetchResult, FetchMethod
from .base import BaseFetcher


logger = logging.getLogger(__name__)

_crawl4ai_import_error: Optional[Exception] = None

try:  # pragma: no cover - optional dependency
    _crawl4ai = importlib.import_module("crawl4ai")
    AsyncWebCrawler = getattr(_crawl4ai, "AsyncWebCrawler", None)
    BrowserConfig = getattr(_crawl4ai, "BrowserConfig", None)
    CrawlerRunConfig = getattr(_crawl4ai, "CrawlerRunConfig", None)
    AsyncPlaywrightCrawlerStrategy = getattr(
        _crawl4ai, "AsyncPlaywrightCrawlerStrategy", None
    )
except Exception as e:
    _crawl4ai_import_error = e
    AsyncWebCrawler = None
    BrowserConfig = None
    CrawlerRunConfig = None
    AsyncPlaywrightCrawlerStrategy = None


class Crawl4AIFetcher(BaseFetcher):
    """
    Crawl4AI 抓取器

    特点：
    - 结合浏览器渲染与内容抽取
    - 返回 HTML / 文本 / Markdown
    - 适用于目录页与内容页
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        crawl4ai_config = self.config.get("crawl4ai", {})
        self._headless = crawl4ai_config.get("headless", True)
        self._wait_for = crawl4ai_config.get("wait_for", 0)
        self._page_timeout_ms = crawl4ai_config.get("page_timeout_ms", self.timeout * 1000)
        self._browser_config = crawl4ai_config.get("browser_config", {})

    @property
    def method(self) -> FetchMethod:
        return FetchMethod.CRAWL4AI

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行 Crawl4AI 抓取

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        start_time = time.time()

        if AsyncWebCrawler is None:
            if _crawl4ai_import_error is not None:
                logger.exception(
                    "[%s] Crawl4AI import failed: %s",
                    task.id,
                    _crawl4ai_import_error,
                )
                error_message = f"crawl4ai import failed: {_crawl4ai_import_error}"
            else:
                logger.error(
                    "[%s] Crawl4AI not available. Please install crawl4ai to use this fetcher.",
                    task.id,
                )
                error_message = "crawl4ai is not installed"

            return self._create_failed_result(
                task=task,
                error_message=error_message,
                start_time=start_time,
            )

        browser_config = None
        if BrowserConfig is not None:
            try:
                browser_config = BrowserConfig(
                    headless=self._headless,
                    user_agent=self._get_user_agent(),
                    **self._browser_config,
                )
            except Exception:
                browser_config = None

        run_config = None
        if CrawlerRunConfig is not None:
            run_config = CrawlerRunConfig()
            for key, value in {
                "page_timeout": self._page_timeout_ms,
                "wait_for": self._wait_for,
            }.items():
                if hasattr(run_config, key):
                    setattr(run_config, key, value)

        try:
            crawler_strategy = None
            if browser_config is not None and AsyncPlaywrightCrawlerStrategy is not None:
                try:
                    crawler_strategy = AsyncPlaywrightCrawlerStrategy(
                        browser_config=browser_config
                    )
                except Exception:
                    crawler_strategy = None

            try:
                if crawler_strategy is not None:
                    crawler_context = AsyncWebCrawler(
                        crawler_strategy=crawler_strategy
                    )
                elif browser_config is not None:
                    crawler_context = AsyncWebCrawler(browser_config=browser_config)
                else:
                    crawler_context = AsyncWebCrawler()
            except TypeError:
                crawler_context = AsyncWebCrawler()

            async with crawler_context as crawler:
                try:
                    if run_config is not None:
                        crawl_result = await crawler.arun(url=task.url, config=run_config)
                    else:
                        crawl_result = await crawler.arun(url=task.url)
                except TypeError:
                    crawl_result = await crawler.arun(task.url)

            html = (
                getattr(crawl_result, "html", None)
                or getattr(crawl_result, "cleaned_html", None)
                or ""
            )
            cleaned_html = getattr(crawl_result, "cleaned_html", None)
            text = getattr(crawl_result, "text", None)
            markdown = getattr(crawl_result, "markdown", None)
            status_code = getattr(crawl_result, "status_code", None) or 200

            if not html and not text:
                logger.warning(
                    "[%s] Crawl4AI returned empty content for %s",
                    task.id,
                    task.url,
                )
                return self._create_failed_result(
                    task=task,
                    error_message="Empty content from Crawl4AI",
                    status_code=status_code,
                    start_time=start_time,
                )

            parsed_data = self._build_parsed_data(task)
            parsed_data["crawl4ai"] = {
                "markdown": markdown,
                "text": text,
                "cleaned_html": cleaned_html,
                "links": getattr(crawl_result, "links", None),
                "title": getattr(crawl_result, "title", None),
            }

            return self._create_success_result(
                task=task,
                html=html,
                status_code=status_code,
                start_time=start_time,
                parsed_data=parsed_data,
                text=text,
            )

        except Exception as e:
            logger.exception("[%s] Crawl4AI fetch failed for %s", task.id, task.url)
            return self._create_failed_result(
                task=task,
                error_message=str(e),
                start_time=start_time,
            )

    async def close(self) -> None:
        """释放资源（Crawl4AI 使用上下文管理，无需常驻资源）"""
        return None

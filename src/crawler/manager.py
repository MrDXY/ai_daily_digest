"""
抓取管理器
统一管理抓取策略，提供稳定可靠的网页抓取能力
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from ..core.models import FetchTask, FetchResult, FetchStatus, FetchMethod
from ..core.config import CrawlerConfig
from .stealth_fetcher import StealthFetcher


logger = logging.getLogger(__name__)


class FetchManager:
    """
    抓取管理器

    特点：
    1. 使用 StealthFetcher 统一处理抓取，内置反爬虫机制
    2. 智能重试和错误恢复
    3. 并发控制和限速
    4. 自动适应不同网站的反爬策略
    """

    def __init__(
        self,
        config: CrawlerConfig,
        cache_dir: Optional[Path] = None,
        cache_enabled: bool = True,
    ):
        self.config = config
        self._fetcher: Optional[StealthFetcher] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def __aenter__(self):
        await self._init_fetcher()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _init_fetcher(self) -> None:
        """初始化抓取器"""
        fetcher_config = {
            "timeout": self.config.timeout,
            "user_agents": self.config.user_agents,
            "playwright": self.config.playwright,
            "crawl4ai": self.config.crawl4ai,
            "stealth": {
                "enable_crawl4ai": True,
                "enable_playwright": True,
                "enable_httpx": True,
                "request_delay": (0.5, 2.0),  # 随机延迟
            },
        }

        self._fetcher = StealthFetcher(fetcher_config)
        self._semaphore = asyncio.Semaphore(self.config.concurrency)

    async def close(self) -> None:
        """关闭抓取器"""
        if self._fetcher:
            await self._fetcher.close()
            self._fetcher = None

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行抓取（带并发控制和重试）

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        async with self._semaphore:
            self._request_count += 1
            result = await self._fetch_with_retry(task)

            if result.status == FetchStatus.SUCCESS:
                self._success_count += 1
            else:
                self._failure_count += 1

            return result

    async def _fetch_with_retry(self, task: FetchTask) -> FetchResult:
        """
        带重试的抓取

        使用指数退避策略进行重试
        """
        last_result: Optional[FetchResult] = None

        for attempt in range(self.config.max_retries):
            try:
                result = await self._fetcher.fetch(task)

                if result.status == FetchStatus.SUCCESS:
                    logger.info(
                        f"[{task.id}] Fetch success (attempt {attempt + 1})"
                    )
                    return result

                last_result = result

                # 检查是否是永久性错误
                if self._is_permanent_error(result):
                    logger.warning(
                        f"[{task.id}] Permanent error, skipping retries: "
                        f"{result.error_message}"
                    )
                    return result

                logger.warning(
                    f"[{task.id}] Fetch failed (attempt {attempt + 1}): "
                    f"{result.error_message}"
                )

                # 等待后重试（指数退避）
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.info(f"[{task.id}] Waiting {delay}s before retry")
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"[{task.id}] Fetch error: {e}")
                last_result = FetchResult(
                    task_id=task.id,
                    url=task.url,
                    status=FetchStatus.FAILED,
                    method=FetchMethod.UNKNOWN,
                    error_message=str(e),
                )

                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        return last_result

    def _is_permanent_error(self, result: FetchResult) -> bool:
        """判断是否是永久性错误（不值得重试）"""
        if result.status_code:
            # 4xx 错误通常是永久性的（429 除外）
            if 400 <= result.status_code < 500 and result.status_code != 429:
                return True

        # 检查错误消息
        error_msg = (result.error_message or "").lower()
        permanent_errors = [
            "not found",
            "page not found",
            "404",
            "401 unauthorized",
            "permission denied",
        ]

        for err in permanent_errors:
            if err in error_msg:
                return True

        return False

    async def fetch_many(
        self,
        tasks: list[FetchTask],
    ) -> list[FetchResult]:
        """
        批量抓取

        Args:
            tasks: 任务列表

        Returns:
            结果列表（与任务顺序对应）
        """
        results = await asyncio.gather(
            *[self.fetch(task) for task in tasks],
            return_exceptions=True,
        )

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(FetchResult(
                    task_id=tasks[i].id,
                    url=tasks[i].url,
                    status=FetchStatus.FAILED,
                    method=FetchMethod.UNKNOWN,
                    error_message=str(result),
                ))
            else:
                processed_results.append(result)

        return processed_results

    def get_stats(self) -> dict[str, Any]:
        """获取抓取统计信息"""
        return {
            "concurrency": self.config.concurrency,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "total_requests": self._request_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": (
                self._success_count / self._request_count * 100
                if self._request_count > 0 else 0
            ),
        }

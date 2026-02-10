"""
抓取管理器
实现轻重结合的抓取策略
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..core.models import FetchTask, FetchResult, FetchStatus, FetchMethod
from ..core.config import CrawlerConfig
from ..core.exceptions import FetchException
from .base import BaseFetcher
from .light_fetcher import LightFetcher
from .heavy_fetcher import HeavyFetcher
from .cache import PageCache


logger = logging.getLogger(__name__)


class FetchManager:
    """
    抓取管理器

    实现轻重结合策略：
    1. 优先使用 LightFetcher (curl_cffi) 快速抓取
    2. 如果失败或内容不完整，自动回退到 HeavyFetcher (Playwright)
    3. 支持重试机制和并发控制
    4. 支持页面缓存，每天只爬取一次
    """

    def __init__(self, config: CrawlerConfig, cache_dir: Optional[Path] = None, cache_enabled: bool = True):
        self.config = config
        self._light_fetcher: Optional[LightFetcher] = None
        self._heavy_fetcher: Optional[HeavyFetcher] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

        # 初始化缓存
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "output" / "cache"
        self._cache = PageCache(cache_dir, enabled=cache_enabled)

    async def __aenter__(self):
        await self._init_fetchers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _init_fetchers(self) -> None:
        """初始化抓取器"""
        fetcher_config = {
            "timeout": self.config.timeout,
            "user_agents": self.config.user_agents,
            "playwright": self.config.playwright,
        }

        self._light_fetcher = LightFetcher(fetcher_config)
        self._heavy_fetcher = HeavyFetcher(fetcher_config)
        self._semaphore = asyncio.Semaphore(self.config.concurrency)

    async def close(self) -> None:
        """关闭所有抓取器"""
        if self._light_fetcher:
            await self._light_fetcher.close()
        if self._heavy_fetcher:
            await self._heavy_fetcher.close()

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行抓取（带并发控制和缓存）

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        # 先检查缓存
        cached_result = self._cache.get(task.url)
        if cached_result is not None:
            # 更新 task_id 以匹配当前任务
            cached_result.task_id = task.id
            logger.info(f"[{task.id}] Using cached result for {task.url}")
            return cached_result

        async with self._semaphore:
            result = await self._fetch_with_fallback(task)

            # 缓存成功的结果
            if result.status == FetchStatus.SUCCESS:
                self._cache.set(task.url, result)

            return result

    async def _fetch_with_fallback(self, task: FetchTask) -> FetchResult:
        """
        轻重结合抓取策略

        1. 检查站点配置，决定是否跳过轻量抓取
        2. 尝试轻量抓取
        3. 如果失败，回退到重量抓取
        """
        site_config = task.site_config.get("fetch", {})
        prefer_light = site_config.get("prefer_light", True)
        requires_js = site_config.get("requires_js", False)

        # 如果需要 JS 渲染，直接使用重量抓取
        if requires_js:
            logger.info(f"[{task.id}] Site requires JS, using heavy fetcher")
            return await self._fetch_with_retry(
                self._heavy_fetcher, task, "heavy"
            )

        # 尝试轻量抓取
        if prefer_light:
            logger.info(f"[{task.id}] Trying light fetcher first")
            result = await self._fetch_with_retry(
                self._light_fetcher, task, "light"
            )

            # 检查是否需要回退
            if self._should_fallback(result, task):
                logger.info(
                    f"[{task.id}] Light fetcher failed or incomplete, "
                    f"falling back to heavy fetcher"
                )
                result = await self._fetch_with_retry(
                    self._heavy_fetcher, task, "heavy"
                )

            return result

        # 直接使用重量抓取
        return await self._fetch_with_retry(self._heavy_fetcher, task, "heavy")

    async def _fetch_with_retry(
        self,
        fetcher: BaseFetcher,
        task: FetchTask,
        fetcher_type: str,
    ) -> FetchResult:
        """
        带重试的抓取

        使用 tenacity 实现指数退避重试
        """
        last_result: Optional[FetchResult] = None

        for attempt in range(self.config.max_retries):
            try:
                result = await fetcher.fetch(task)

                if result.status == FetchStatus.SUCCESS:
                    logger.info(
                        f"[{task.id}] Fetch success with {fetcher_type} "
                        f"(attempt {attempt + 1})"
                    )
                    return result

                last_result = result

                # 某些错误不值得重试
                if self._is_permanent_error(result):
                    logger.warning(
                        f"[{task.id}] Permanent error, skipping retries: "
                        f"{result.error_message}"
                    )
                    return result

                # 等待后重试
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.info(
                        f"[{task.id}] Retry {attempt + 1} failed, "
                        f"waiting {delay}s before next attempt"
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"[{task.id}] Fetch error: {e}")
                last_result = FetchResult(
                    task_id=task.id,
                    url=task.url,
                    status=FetchStatus.FAILED,
                    method=fetcher.method,
                    error_message=str(e),
                )

                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        return last_result

    def _should_fallback(self, result: FetchResult, task: FetchTask) -> bool:
        """
        判断是否需要回退到重量抓取

        回退条件：
        1. 抓取失败
        2. 内容太短（可能是反爬页面）
        3. 缺少关键内容标记
        """
        if result.status != FetchStatus.SUCCESS:
            return True

        if not result.html:
            return True

        # 内容长度检查
        if len(result.html) < 1000:
            return True

        # 检查站点配置中定义的必需元素
        site_config = task.site_config.get("list_parser", {})
        container_selector = site_config.get("container")

        if container_selector:
            # 简单检查容器标记是否存在
            # 这里用简单的字符串检查，完整的 DOM 解析在 processor 中进行
            container_tag = container_selector.split(".")[0].split("#")[0]
            if container_tag and container_tag not in result.html.lower():
                return True

        return False

    def _is_permanent_error(self, result: FetchResult) -> bool:
        """判断是否是永久性错误（不值得重试）"""
        if result.status_code:
            # 4xx 错误通常是永久性的
            if 400 <= result.status_code < 500:
                # 429 (Too Many Requests) 可以重试
                if result.status_code != 429:
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
        # 使用 gather 并发执行
        results = await asyncio.gather(
            *[self.fetch(task) for task in tasks],
            return_exceptions=True,
        )

        # 处理异常
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
            "cache": self._cache.get_stats(),
        }

    def clear_old_cache(self, keep_days: int = 7) -> int:
        """
        清理旧的缓存

        Args:
            keep_days: 保留最近几天的缓存

        Returns:
            删除的文件数量
        """
        return self._cache.clear_old(keep_days)

    @property
    def cache(self) -> PageCache:
        """获取缓存管理器实例"""
        return self._cache

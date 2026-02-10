"""
轻量级抓取器
使用 curl_cffi 实现快速抓取，支持 impersonate 绕过检测
"""

import asyncio
import time
from typing import Any, Optional

from curl_cffi.requests import AsyncSession, Response

from ..core.models import FetchTask, FetchResult, FetchMethod
from ..core.exceptions import FetchException
from .base import BaseFetcher


class LightFetcher(BaseFetcher):
    """
    轻量级抓取器

    特点：
    - 基于 curl_cffi，支持 TLS 指纹模拟
    - 速度快，资源占用低
    - 不支持 JavaScript 渲染
    """

    # 支持的浏览器指纹
    IMPERSONATE_OPTIONS = [
        "chrome120",
        "chrome119",
        "chrome110",
        "safari17_0",
        "edge101",
    ]

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        self._session: Optional[AsyncSession] = None
        self._impersonate = self.config.get("impersonate", "chrome120")

    @property
    def method(self) -> FetchMethod:
        return FetchMethod.LIGHT

    async def _get_session(self) -> AsyncSession:
        """获取或创建会话"""
        if self._session is None:
            self._session = AsyncSession(
                impersonate=self._impersonate,
                timeout=self.timeout,
            )
        return self._session

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行轻量级抓取

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        start_time = time.time()

        try:
            session = await self._get_session()

            # 构建请求头
            headers = {
                "User-Agent": self._get_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            # 合并自定义头
            if task.metadata.get("headers"):
                headers.update(task.metadata["headers"])

            # 发起请求
            response: Response = await session.get(
                task.url,
                headers=headers,
                allow_redirects=True,
            )

            # 检查响应状态
            if response.status_code >= 400:
                return self._create_failed_result(
                    task=task,
                    error_message=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    start_time=start_time,
                )

            # 获取内容
            html = response.text

            # 检查内容有效性
            if not self._is_valid_content(html, task):
                return self._create_failed_result(
                    task=task,
                    error_message="Content validation failed (possible anti-bot)",
                    status_code=response.status_code,
                    start_time=start_time,
                )

            return self._create_success_result(
                task=task,
                html=html,
                status_code=response.status_code,
                start_time=start_time,
            )

        except asyncio.TimeoutError:
            return self._create_failed_result(
                task=task,
                error_message="Request timeout",
                start_time=start_time,
            )

        except Exception as e:
            return self._create_failed_result(
                task=task,
                error_message=str(e),
                start_time=start_time,
            )

    def _is_valid_content(self, html: str, task: FetchTask) -> bool:
        """
        验证内容有效性
        检测常见的反爬标志
        """
        if not html or len(html) < 100:
            return False

        # 检测常见的反爬/验证页面标志
        anti_bot_markers = [
            "captcha",
            "cf-browser-verification",
            "challenge-running",
            "just a moment",
            "checking your browser",
            "access denied",
            "403 forbidden",
        ]

        html_lower = html.lower()
        for marker in anti_bot_markers:
            if marker in html_lower:
                # 如果是简单的 403 页面
                if len(html) < 5000:
                    return False

        return True

    async def close(self) -> None:
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None

    async def fetch_many(
        self,
        tasks: list[FetchTask],
        concurrency: int = 5,
    ) -> list[FetchResult]:
        """
        批量抓取

        Args:
            tasks: 任务列表
            concurrency: 并发数

        Returns:
            结果列表
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(task: FetchTask) -> FetchResult:
            async with semaphore:
                return await self.fetch(task)

        results = await asyncio.gather(
            *[fetch_with_semaphore(task) for task in tasks],
            return_exceptions=True,
        )

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(self._create_failed_result(
                    task=tasks[i],
                    error_message=str(result),
                ))
            else:
                processed_results.append(result)

        return processed_results

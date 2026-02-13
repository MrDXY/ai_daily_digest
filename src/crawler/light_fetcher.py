"""
轻量级抓取器
使用 curl_cffi 实现快速抓取，支持 impersonate 绕过检测

注意：curl_cffi 在部分平台（例如 macOS）可能因为本地动态库缺失而无法导入。
本模块会在运行时探测 curl_cffi 是否可用，不可用时自动回退到 httpx。
"""

import asyncio
import time
from typing import Any, Optional, TYPE_CHECKING

import httpx

from ..core.models import FetchTask, FetchResult, FetchMethod
from .base import BaseFetcher

if TYPE_CHECKING:  # pragma: no cover
    from curl_cffi.requests import AsyncSession, Response


def _try_import_curl_cffi():
    """Try importing curl_cffi; return (AsyncSession, Response, error_message)."""
    try:
        from curl_cffi.requests import AsyncSession, Response  # type: ignore

        return AsyncSession, Response, None
    except Exception as e:  # ImportError / OSError / dlopen errors
        return None, None, str(e)


class LightFetcher(BaseFetcher):
    """
    轻量级抓取器

    特点：
    - 优先使用 curl_cffi，支持 TLS 指纹模拟
    - 当 curl_cffi 不可用时，自动回退到 httpx（不支持指纹伪装）
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
        self._session = None
        self._httpx_client: Optional[httpx.AsyncClient] = None
        self._impersonate = self.config.get("impersonate", "chrome120")
        self._curl_import_error: Optional[str] = None

    @property
    def method(self) -> FetchMethod:
        return FetchMethod.LIGHT

    @classmethod
    def is_curl_cffi_available(cls) -> bool:
        AsyncSession, _, err = _try_import_curl_cffi()
        return AsyncSession is not None and err is None

    async def _get_session(self):
        """获取或创建 curl_cffi 会话（如果可用）。"""
        if self._session is not None:
            return self._session

        AsyncSession, _, err = _try_import_curl_cffi()
        if AsyncSession is None:
            self._curl_import_error = err or "curl_cffi import failed"
            return None

        self._session = AsyncSession(
            impersonate=self._impersonate,
            timeout=self.timeout,
        )
        return self._session

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端（回退方案）。"""
        if self._httpx_client is None:
            timeout = httpx.Timeout(self.timeout)
            self._httpx_client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": self._get_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                },
            )
        return self._httpx_client

    async def fetch(self, task: FetchTask) -> FetchResult:
        start_time = time.time()

        # 构建请求头
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if task.metadata.get("headers"):
            headers.update(task.metadata["headers"])

        try:
            session = await self._get_session()

            if session is not None:
                # 发起请求 (curl_cffi)
                response = await session.get(
                    task.url,
                    headers=headers,
                    allow_redirects=True,
                )

                status_code = getattr(response, "status_code", None)
                text = getattr(response, "text", "")
            else:
                # 回退到 httpx
                client = await self._get_httpx_client()
                r = await client.get(task.url, headers=headers)
                status_code = r.status_code
                text = r.text

            if status_code is None:
                return self._create_failed_result(
                    task=task,
                    error_message="No status_code in response",
                    start_time=start_time,
                )

            # 检查响应状态
            if status_code >= 400:
                return self._create_failed_result(
                    task=task,
                    error_message=f"HTTP {status_code}",
                    status_code=status_code,
                    start_time=start_time,
                )

            html = text
            if not self._is_valid_content(html, task):
                note = "Content validation failed (possible anti-bot)"
                if session is None and self._curl_import_error:
                    note += f"; curl_cffi unavailable: {self._curl_import_error}"
                return self._create_failed_result(
                    task=task,
                    error_message=note,
                    status_code=status_code,
                    start_time=start_time,
                )

            return self._create_success_result(
                task=task,
                html=html,
                status_code=status_code,
                start_time=start_time,
            )

        except asyncio.TimeoutError:
            return self._create_failed_result(
                task=task,
                error_message="Request timeout",
                start_time=start_time,
            )

        except httpx.TimeoutException:
            return self._create_failed_result(
                task=task,
                error_message="Request timeout",
                start_time=start_time,
            )

        except Exception as e:
            msg = str(e)
            if self._curl_import_error and "curl_cffi" in msg.lower():
                msg = f"{msg}; curl_cffi unavailable: {self._curl_import_error}"
            return self._create_failed_result(
                task=task,
                error_message=msg,
                start_time=start_time,
            )

    def _is_valid_content(self, html: str, task: FetchTask) -> bool:
        if not html or len(html) < 100:
            return False

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
                if len(html) < 5000:
                    return False

        return True

    async def close(self) -> None:
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None
        if self._httpx_client:
            await self._httpx_client.aclose()
            self._httpx_client = None

    async def fetch_many(
        self,
        tasks: list[FetchTask],
        concurrency: int = 5,
    ) -> list[FetchResult]:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(task: FetchTask) -> FetchResult:
            async with semaphore:
                return await self.fetch(task)

        results = await asyncio.gather(
            *[fetch_with_semaphore(task) for task in tasks],
            return_exceptions=True,
        )

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    self._create_failed_result(
                        task=tasks[i],
                        error_message=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

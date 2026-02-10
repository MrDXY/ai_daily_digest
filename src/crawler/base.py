"""
爬虫抽象基类
定义统一的抓取接口
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..core.models import FetchTask, FetchResult, FetchStatus, FetchMethod


class BaseFetcher(ABC):
    """
    爬虫抽象基类
    所有具体爬虫实现必须继承此类
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 30)
        self.user_agents = self.config.get("user_agents", [])

    @property
    @abstractmethod
    def method(self) -> FetchMethod:
        """返回抓取方式标识"""
        pass

    @abstractmethod
    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行抓取

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """释放资源"""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _create_success_result(
        self,
        task: FetchTask,
        html: str,
        status_code: int,
        start_time: float,
    ) -> FetchResult:
        """创建成功结果"""
        return FetchResult(
            task_id=task.id,
            url=task.url,
            status=FetchStatus.SUCCESS,
            method=self.method,
            html=html,
            status_code=status_code,
            response_time_ms=(time.time() - start_time) * 1000,
        )

    def _create_failed_result(
        self,
        task: FetchTask,
        error_message: str,
        status_code: Optional[int] = None,
        start_time: Optional[float] = None,
    ) -> FetchResult:
        """创建失败结果"""
        response_time = None
        if start_time:
            response_time = (time.time() - start_time) * 1000

        return FetchResult(
            task_id=task.id,
            url=task.url,
            status=FetchStatus.FAILED,
            method=self.method,
            status_code=status_code,
            error_message=error_message,
            response_time_ms=response_time,
        )

    def _get_user_agent(self) -> str:
        """获取随机 User-Agent"""
        import random
        if self.user_agents:
            return random.choice(self.user_agents)
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

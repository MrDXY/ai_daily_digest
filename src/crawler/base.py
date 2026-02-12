"""
爬虫抽象基类
定义统一的抓取接口
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..core.models import (
    FetchTask,
    FetchResult,
    FetchStatus,
    FetchMethod,
    FetchPageType,
)


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
        page_type: Optional[FetchPageType] = None,
        parsed_data: Optional[dict[str, Any]] = None,
        text: Optional[str] = None,
    ) -> FetchResult:
        """创建成功结果"""
        return FetchResult(
            task_id=task.id,
            url=task.url,
            status=FetchStatus.SUCCESS,
            method=self.method,
            page_type=page_type or self._infer_page_type(task),
            html=html,
            text=text,
            parsed_data=parsed_data or self._build_parsed_data(task),
            status_code=status_code,
            response_time_ms=(time.time() - start_time) * 1000,
        )

    def _create_failed_result(
        self,
        task: FetchTask,
        error_message: str,
        status_code: Optional[int] = None,
        start_time: Optional[float] = None,
        page_type: Optional[FetchPageType] = None,
        parsed_data: Optional[dict[str, Any]] = None,
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
            page_type=page_type or self._infer_page_type(task),
            status_code=status_code,
            error_message=error_message,
            response_time_ms=response_time,
            parsed_data=parsed_data or self._build_parsed_data(task),
        )

    def _infer_page_type(self, task: FetchTask) -> FetchPageType:
        """根据站点配置推断页面类型"""
        explicit = task.metadata.get("page_type") or task.site_config.get("page_type")
        if explicit:
            explicit_value = str(explicit).lower()
            if explicit_value in ("list", "structured"):
                return FetchPageType.LIST
            if explicit_value in ("content", "article"):
                return FetchPageType.CONTENT

        site_info = task.site_config.get("site", {})
        site_type = site_info.get("type", "structured")
        list_parser = task.site_config.get("list_parser", {})

        if site_type == "article" or not list_parser:
            return FetchPageType.CONTENT

        return FetchPageType.LIST

    def _build_parsed_data(self, task: FetchTask) -> dict[str, Any]:
        """构建通用解析元数据"""
        parsed_data: dict[str, Any] = {}

        list_parser = task.site_config.get("list_parser", {})
        if list_parser:
            parsed_data["list_parser"] = self._sanitize_list_parser(list_parser)

        fetch_config = task.site_config.get("fetch", {})
        if fetch_config:
            parsed_data["fetch"] = fetch_config

        return parsed_data

    def _sanitize_list_parser(self, list_parser: dict[str, Any]) -> dict[str, Any]:
        """过滤不支持的列表选择器配置"""
        selectors = list_parser.get("selectors", {})
        if not isinstance(selectors, dict):
            return list_parser

        valid_selectors = {
            k: v for k, v in selectors.items()
            if v and not str(v).strip().startswith("+")
        }

        sanitized = dict(list_parser)
        sanitized["selectors"] = valid_selectors
        return sanitized

    def _get_user_agent(self) -> str:
        """获取随机 User-Agent"""
        import random
        if self.user_agents:
            return random.choice(self.user_agents)
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

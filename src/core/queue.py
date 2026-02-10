"""
异步任务队列
支持本地 asyncio 和 Ray 分布式两种模式
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

from .models import FetchTask, FetchResult

T = TypeVar("T")


class BaseTaskQueue(ABC, Generic[T]):
    """任务队列抽象基类"""

    @abstractmethod
    async def put(self, item: T) -> None:
        """放入任务"""
        pass

    @abstractmethod
    async def get(self) -> T:
        """获取任务"""
        pass

    @abstractmethod
    async def task_done(self) -> None:
        """标记任务完成"""
        pass

    @abstractmethod
    def empty(self) -> bool:
        """队列是否为空"""
        pass

    @abstractmethod
    def qsize(self) -> int:
        """队列大小"""
        pass


class AsyncTaskQueue(BaseTaskQueue[T]):
    """
    本地异步任务队列
    基于 asyncio.Queue 实现
    """

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)

    async def put(self, item: T) -> None:
        await self._queue.put(item)

    async def get(self) -> T:
        return await self._queue.get()

    async def task_done(self) -> None:
        self._queue.task_done()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()

    async def join(self) -> None:
        """等待所有任务完成"""
        await self._queue.join()

    async def put_many(self, items: list[T]) -> None:
        """批量放入任务"""
        for item in items:
            await self._queue.put(item)

    async def get_nowait(self) -> Optional[T]:
        """非阻塞获取"""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


class PriorityTaskQueue(BaseTaskQueue[T]):
    """
    优先级任务队列
    支持按优先级排序
    """

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.PriorityQueue[tuple[int, T]] = asyncio.PriorityQueue(maxsize=maxsize)
        self._counter = 0  # 用于保证 FIFO 顺序

    async def put(self, item: T, priority: int = 0) -> None:
        """
        放入任务

        Args:
            item: 任务项
            priority: 优先级，数字越小优先级越高
        """
        self._counter += 1
        await self._queue.put((priority, self._counter, item))

    async def get(self) -> T:
        priority, _, item = await self._queue.get()
        return item

    async def task_done(self) -> None:
        self._queue.task_done()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()


# ============================================
# Ray 分布式队列适配器 (可选)
# ============================================

class RayTaskQueue(BaseTaskQueue[T]):
    """
    Ray 分布式任务队列
    用于 KubeRay 环境

    注意：需要安装 ray 包
    """

    def __init__(self, maxsize: int = 0):
        try:
            import ray
            from ray.util.queue import Queue as RayQueue
            self._queue = RayQueue(maxsize=maxsize)
            self._ray = ray
        except ImportError:
            raise ImportError(
                "Ray is not installed. Install with: pip install ray[default]"
            )

    async def put(self, item: T) -> None:
        # Ray Queue 的 put 是同步的，需要在线程池中执行
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._queue.put, item)

    async def get(self) -> T:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._queue.get)

    async def task_done(self) -> None:
        # Ray Queue 没有 task_done，跳过
        pass

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.size()


def create_queue(
    queue_type: str = "local",
    maxsize: int = 0,
    **kwargs
) -> BaseTaskQueue:
    """
    队列工厂函数

    Args:
        queue_type: 队列类型 ("local", "priority", "ray")
        maxsize: 最大队列大小

    Returns:
        任务队列实例
    """
    if queue_type == "local":
        return AsyncTaskQueue(maxsize=maxsize)
    elif queue_type == "priority":
        return PriorityTaskQueue(maxsize=maxsize)
    elif queue_type == "ray":
        return RayTaskQueue(maxsize=maxsize)
    else:
        raise ValueError(f"Unknown queue type: {queue_type}")

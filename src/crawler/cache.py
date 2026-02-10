"""
页面缓存模块
实现每日抓取内容的本地缓存，避免重复爬取
"""

import hashlib
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Any

from ..core.models import FetchResult, FetchStatus, FetchMethod


logger = logging.getLogger(__name__)


class PageCache:
    """
    页面缓存管理器

    缓存策略：
    - 以日期为粒度，每天的缓存独立存储
    - 使用 URL 的 hash 作为文件名
    - 支持缓存过期和清理
    """

    def __init__(self, cache_dir: Path, enabled: bool = True):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径
            enabled: 是否启用缓存
        """
        self.cache_dir = cache_dir
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_url_hash(self, url: str) -> str:
        """生成 URL 的唯一标识"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def _get_today_dir(self) -> Path:
        """获取今天的缓存目录"""
        today = date.today().isoformat()
        today_dir = self.cache_dir / today
        today_dir.mkdir(parents=True, exist_ok=True)
        return today_dir

    def _get_cache_path(self, url: str, cache_date: Optional[date] = None) -> Path:
        """获取缓存文件路径"""
        if cache_date is None:
            cache_date = date.today()

        date_dir = self.cache_dir / cache_date.isoformat()
        url_hash = self._get_url_hash(url)
        return date_dir / f"{url_hash}.json"

    def get(self, url: str, cache_date: Optional[date] = None) -> Optional[FetchResult]:
        """
        从缓存获取页面内容

        Args:
            url: 页面 URL
            cache_date: 缓存日期，默认为今天

        Returns:
            缓存的 FetchResult，如果不存在则返回 None
        """
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(url, cache_date)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复 FetchResult 对象
            result = FetchResult(
                task_id=data.get('task_id', ''),
                url=data.get('url', url),
                status=FetchStatus(data.get('status', 'success')),
                method=FetchMethod(data.get('method', 'unknown')),
                html=data.get('html'),
                text=data.get('text'),
                title=data.get('title'),
                description=data.get('description'),
                parsed_data=data.get('parsed_data', {}),
                status_code=data.get('status_code'),
                response_time_ms=data.get('response_time_ms'),
                error_message=data.get('error_message'),
            )

            logger.info(f"Cache hit for {url}")
            return result

        except Exception as e:
            logger.warning(f"Failed to read cache for {url}: {e}")
            return None

    def set(self, url: str, result: FetchResult) -> bool:
        """
        将页面内容存入缓存

        Args:
            url: 页面 URL
            result: 抓取结果

        Returns:
            是否保存成功
        """
        if not self.enabled:
            return False

        # 只缓存成功的结果
        if result.status != FetchStatus.SUCCESS:
            return False

        cache_path = self._get_cache_path(url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 序列化 FetchResult
            data = {
                'task_id': result.task_id,
                'url': result.url,
                'status': result.status.value if isinstance(result.status, FetchStatus) else result.status,
                'method': result.method.value if isinstance(result.method, FetchMethod) else result.method,
                'html': result.html,
                'text': result.text,
                'title': result.title,
                'description': result.description,
                'parsed_data': result.parsed_data,
                'status_code': result.status_code,
                'response_time_ms': result.response_time_ms,
                'error_message': result.error_message,
                'cached_at': datetime.now().isoformat(),
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Cached page for {url}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache page for {url}: {e}")
            return False

    def has(self, url: str, cache_date: Optional[date] = None) -> bool:
        """
        检查是否存在缓存

        Args:
            url: 页面 URL
            cache_date: 缓存日期，默认为今天

        Returns:
            是否存在缓存
        """
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(url, cache_date)
        return cache_path.exists()

    def delete(self, url: str, cache_date: Optional[date] = None) -> bool:
        """
        删除指定 URL 的缓存

        Args:
            url: 页面 URL
            cache_date: 缓存日期，默认为今天

        Returns:
            是否删除成功
        """
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(url, cache_date)

        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.info(f"Deleted cache for {url}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete cache for {url}: {e}")
                return False

        return False

    def clear_date(self, cache_date: date) -> int:
        """
        清理指定日期的所有缓存

        Args:
            cache_date: 要清理的日期

        Returns:
            删除的文件数量
        """
        date_dir = self.cache_dir / cache_date.isoformat()

        if not date_dir.exists():
            return 0

        count = 0
        try:
            for cache_file in date_dir.glob("*.json"):
                cache_file.unlink()
                count += 1

            # 删除空目录
            if not any(date_dir.iterdir()):
                date_dir.rmdir()

            logger.info(f"Cleared {count} cached files for {cache_date}")

        except Exception as e:
            logger.error(f"Failed to clear cache for {cache_date}: {e}")

        return count

    def clear_old(self, keep_days: int = 7) -> int:
        """
        清理旧的缓存

        Args:
            keep_days: 保留最近几天的缓存

        Returns:
            删除的文件数量
        """
        if not self.cache_dir.exists():
            return 0

        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=keep_days)

        total_count = 0
        try:
            for date_dir in self.cache_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                try:
                    dir_date = date.fromisoformat(date_dir.name)
                    if dir_date < cutoff_date:
                        count = self.clear_date(dir_date)
                        total_count += count
                except ValueError:
                    # 不是日期格式的目录，跳过
                    continue

        except Exception as e:
            logger.error(f"Failed to clear old cache: {e}")

        if total_count > 0:
            logger.info(f"Cleared {total_count} old cached files")

        return total_count

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        if not self.cache_dir.exists():
            return {
                'enabled': self.enabled,
                'total_files': 0,
                'total_size_mb': 0,
                'dates': [],
            }

        total_files = 0
        total_size = 0
        dates = []

        for date_dir in sorted(self.cache_dir.iterdir()):
            if not date_dir.is_dir():
                continue

            try:
                dir_date = date.fromisoformat(date_dir.name)
                file_count = len(list(date_dir.glob("*.json")))
                dir_size = sum(f.stat().st_size for f in date_dir.glob("*.json"))

                dates.append({
                    'date': date_dir.name,
                    'files': file_count,
                    'size_mb': round(dir_size / 1024 / 1024, 2),
                })

                total_files += file_count
                total_size += dir_size

            except ValueError:
                continue

        return {
            'enabled': self.enabled,
            'total_files': total_files,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'dates': dates,
        }

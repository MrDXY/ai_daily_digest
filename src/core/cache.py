"""
通用缓存组件

提供可复用的 JSON 缓存能力，支持：
- 以日期为粒度的本地缓存
- URL hash 作为缓存键
- 过期清理与统计
"""

import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any

from .models import FetchResult, FetchStatus, FetchMethod, FetchPageType


logger = logging.getLogger(__name__)


class DailyJSONCache:
    """
    通用 JSON 缓存基类

    缓存策略：
    - 以日期为粒度，每天的缓存独立存储
    - 使用 URL 的 hash 作为文件名
    """

    def __init__(self, cache_dir: Path, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def _get_cache_path(self, url: str, cache_date: Optional[date] = None) -> Path:
        if cache_date is None:
            cache_date = date.today()

        date_dir = self.cache_dir / cache_date.isoformat()
        url_hash = self._get_url_hash(url)
        return date_dir / f"{url_hash}.json"

    def _read_json(self, cache_path: Path) -> Optional[dict[str, Any]]:
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_path}: {e}")
            return None

    def _write_json(self, cache_path: Path, data: dict[str, Any]) -> bool:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to write cache file {cache_path}: {e}")
            return False

    def has(self, url: str, cache_date: Optional[date] = None) -> bool:
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(url, cache_date)
        return cache_path.exists()

    def delete(self, url: str, cache_date: Optional[date] = None) -> bool:
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(url, cache_date)
        if cache_path.exists():
            try:
                cache_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete cache for {url}: {e}")
                return False

        return False

    def clear_date(self, cache_date: date) -> int:
        date_dir = self.cache_dir / cache_date.isoformat()
        if not date_dir.exists():
            return 0

        count = 0
        try:
            for cache_file in date_dir.glob("*.json"):
                cache_file.unlink()
                count += 1

            if not any(date_dir.iterdir()):
                date_dir.rmdir()

        except Exception as e:
            logger.error(f"Failed to clear cache for {cache_date}: {e}")

        return count

    def clear_old(self, keep_days: int = 7) -> int:
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
                    continue
        except Exception as e:
            logger.error(f"Failed to clear old cache: {e}")

        return total_count

    def get_stats(self) -> dict[str, Any]:
        if not self.cache_dir.exists():
            return {
                "enabled": self.enabled,
                "total_files": 0,
                "total_size_mb": 0,
                "dates": [],
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

                dates.append(
                    {
                        "date": date_dir.name,
                        "files": file_count,
                        "size_mb": round(dir_size / 1024 / 1024, 2),
                    }
                )

                total_files += file_count
                total_size += dir_size

            except ValueError:
                continue

        return {
            "enabled": self.enabled,
            "total_files": total_files,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "dates": dates,
        }


class PageCache(DailyJSONCache):
    """
    页面缓存管理器

    仅缓存成功的 FetchResult
    """

    def get(self, url: str, cache_date: Optional[date] = None) -> Optional[FetchResult]:
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(url, cache_date)
        data = self._read_json(cache_path)
        if not data:
            return None

        try:
            result = FetchResult(
                task_id=data.get("task_id", ""),
                url=data.get("url", url),
                status=FetchStatus(data.get("status", "success")),
                method=FetchMethod(data.get("method", "unknown")),
                page_type=FetchPageType(data.get("page_type", "unknown")),
                html=data.get("html"),
                text=data.get("text"),
                title=data.get("title"),
                description=data.get("description"),
                parsed_data=data.get("parsed_data", {}),
                status_code=data.get("status_code"),
                response_time_ms=data.get("response_time_ms"),
                error_message=data.get("error_message"),
            )

            logger.info(f"Cache hit for {url}")
            return result

        except Exception as e:
            logger.warning(f"Failed to restore cache for {url}: {e}")
            return None

    def set(self, url: str, result: FetchResult) -> bool:
        if not self.enabled:
            return False

        if result.status != FetchStatus.SUCCESS:
            return False

        cache_path = self._get_cache_path(url)

        data = {
            "task_id": result.task_id,
            "url": result.url,
            "status": result.status.value if isinstance(result.status, FetchStatus) else result.status,
            "method": result.method.value if isinstance(result.method, FetchMethod) else result.method,
            "page_type": result.page_type.value if isinstance(result.page_type, FetchPageType) else result.page_type,
            "html": result.html,
            "text": result.text,
            "title": result.title,
            "description": result.description,
            "parsed_data": result.parsed_data,
            "status_code": result.status_code,
            "response_time_ms": result.response_time_ms,
            "error_message": result.error_message,
            "cached_at": datetime.now().isoformat(),
        }

        if self._write_json(cache_path, data):
            logger.info(f"Cached page for {url}")
            return True

        return False


class AIPayloadCache(DailyJSONCache):
    """
    AI Payload 缓存管理器

    仅缓存发送给 AI 的 payload
    """

    def get(self, url: str, cache_date: Optional[date] = None) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(url, cache_date)
        data = self._read_json(cache_path)
        if not data:
            return None

        payload = data.get("payload")
        if not isinstance(payload, dict):
            return None

        logger.info(f"AI payload cache hit for {url}")
        return payload

    def set(self, url: str, payload: dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        if not payload or not payload.get("content"):
            return False

        cache_path = self._get_cache_path(url)
        data = {
            "url": url,
            "payload": payload,
            "cached_at": datetime.now().isoformat(),
        }

        if self._write_json(cache_path, data):
            logger.info(f"Cached AI payload for {url}")
            return True

        return False


class AISummaryCache(DailyJSONCache):
    """
    AI 摘要结果缓存管理器

    仅缓存 AI 输出的结构化结果
    """

    def get(self, url: str, cache_date: Optional[date] = None) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(url, cache_date)
        data = self._read_json(cache_path)
        if not data:
            return None

        summary = data.get("summary")
        if not isinstance(summary, dict):
            return None

        logger.info(f"AI summary cache hit for {url}")
        return summary

    def set(self, url: str, summary: dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        if not summary or not summary.get("summary"):
            return False

        cache_path = self._get_cache_path(url)
        data = {
            "url": url,
            "summary": summary,
            "cached_at": datetime.now().isoformat(),
        }

        if self._write_json(cache_path, data):
            logger.info(f"Cached AI summary for {url}")
            return True

        return False

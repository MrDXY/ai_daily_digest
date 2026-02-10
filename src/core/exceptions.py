"""
自定义异常类
提供清晰的错误分类和上下文信息
"""

from typing import Any, Optional


class DigestException(Exception):
    """基础异常类"""

    def __init__(
        self,
        message: str,
        *,
        cause: Optional[Exception] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.context = context or {}

    def __str__(self) -> str:
        parts = [self.message]
        if self.cause:
            parts.append(f"Caused by: {self.cause}")
        if self.context:
            parts.append(f"Context: {self.context}")
        return " | ".join(parts)


class FetchException(DigestException):
    """抓取异常"""

    def __init__(
        self,
        message: str,
        *,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.url = url
        self.status_code = status_code
        if url:
            self.context["url"] = url
        if status_code:
            self.context["status_code"] = status_code


class ParseException(DigestException):
    """解析异常"""

    def __init__(
        self,
        message: str,
        *,
        selector: Optional[str] = None,
        html_snippet: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.selector = selector
        if selector:
            self.context["selector"] = selector
        if html_snippet:
            self.context["html_snippet"] = html_snippet[:200]


class AIException(DigestException):
    """AI 调用异常"""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.provider = provider
        self.model = model
        if provider:
            self.context["provider"] = provider
        if model:
            self.context["model"] = model


class ConfigException(DigestException):
    """配置异常"""
    pass


class RateLimitException(AIException):
    """API 限流异常"""

    def __init__(
        self,
        message: str,
        *,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after"] = retry_after

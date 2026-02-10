"""
AI 摘要器
支持多种 AI 模型后端：Claude, OpenAI, Azure OpenAI, 自定义模型
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..core.config import AIConfig, ClaudeConfig, OpenAIConfig, AzureOpenAIConfig, CustomModelConfig
from ..core.models import Article
from ..core.exceptions import AIException, RateLimitException


logger = logging.getLogger(__name__)


# ============================================
# 摘要 Prompt 模板
# ============================================

DIGEST_PROMPT = """你是一个专业的技术内容分析师。请分析以下技术项目/文章，并提供结构化的摘要。

## 输入内容
标题: {title}
来源: {source}
描述: {description}
正文内容:
{content}

## 任务要求
请提供以下信息（JSON 格式）：

1. **summary**: 用 2-3 句话概括项目/文章的核心内容（中文）
2. **core_value**: 这个项目/文章的核心价值是什么？解决了什么问题？（1-2 句话）
3. **tech_stack**: 涉及的主要技术栈（列表形式，如 ["Python", "FastAPI", "PostgreSQL"]）
4. **recommendation**: 推荐理由，为什么值得关注？（1-2 句话）
5. **score**: 综合评分 (0-10)，评分标准：
   - 创新性 (0-3分): 是否有新颖的想法或方法
   - 实用性 (0-3分): 是否能解决实际问题
   - 技术深度 (0-2分): 技术实现的复杂度和质量
   - 社区热度 (0-2分): 关注度、star 数、讨论热度

## 输出格式
请直接输出 JSON，不要包含其他内容：
```json
{{
  "summary": "...",
  "core_value": "...",
  "tech_stack": ["...", "..."],
  "recommendation": "...",
  "score": 8.5
}}
```
"""


# ============================================
# 基础 AI Provider 接口
# ============================================

class BaseAIProvider(ABC):
    """AI Provider 基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        执行补全

        Args:
            prompt: 用户 prompt
            system_prompt: 系统 prompt

        Returns:
            模型响应文本
        """
        pass

    async def close(self) -> None:
        """释放资源"""
        pass


# ============================================
# Claude Provider
# ============================================

class ClaudeProvider(BaseAIProvider):
    """Claude API Provider"""

    def __init__(self, config: ClaudeConfig):
        self.config = config
        self._client = None

    @property
    def name(self) -> str:
        return "claude"

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            client = self._get_client()

            messages = [{"role": "user", "content": prompt}]

            response = await client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt or "You are a helpful assistant.",
                messages=messages,
            )

            return response.content[0].text

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                raise RateLimitException(
                    f"Claude rate limit exceeded",
                    provider=self.name,
                    model=self.config.model,
                    cause=e,
                )
            raise AIException(
                f"Claude API error: {e}",
                provider=self.name,
                model=self.config.model,
                cause=e,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


# ============================================
# OpenAI Provider
# ============================================

class OpenAIProvider(BaseAIProvider):
    """OpenAI API Provider"""

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.config.api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                raise RateLimitException(
                    f"OpenAI rate limit exceeded",
                    provider=self.name,
                    model=self.config.model,
                    cause=e,
                )
            raise AIException(
                f"OpenAI API error: {e}",
                provider=self.name,
                model=self.config.model,
                cause=e,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


# ============================================
# Azure OpenAI Provider
# ============================================

class AzureOpenAIProvider(BaseAIProvider):
    """Azure OpenAI API Provider"""

    def __init__(self, config: AzureOpenAIConfig):
        self.config = config
        self._client = None

    @property
    def name(self) -> str:
        return "azure_openai"

    def _get_client(self):
        if self._client is None:
            from openai import AsyncAzureOpenAI
            self._client = AsyncAzureOpenAI(
                api_key=self.config.api_key,
                api_version=self.config.api_version,
                azure_endpoint=self.config.api_base,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.config.deployment_name,  # Azure 使用 deployment name
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise RateLimitException(
                    f"Azure OpenAI rate limit exceeded",
                    provider=self.name,
                    model=self.config.deployment_name,
                    cause=e,
                )
            raise AIException(
                f"Azure OpenAI API error: {e}",
                provider=self.name,
                model=self.config.deployment_name,
                cause=e,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


# ============================================
# Custom Model Provider (兼容 OpenAI API 格式)
# ============================================

class CustomModelProvider(BaseAIProvider):
    """
    自定义模型 Provider
    支持任何兼容 OpenAI API 格式的模型服务
    如：vLLM, LocalAI, Ollama, 自建服务等
    """

    def __init__(self, config: CustomModelConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "custom"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
            }

            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            # 合并额外请求头
            if self.config.extra_headers:
                headers.update(self.config.extra_headers)

            self._client = httpx.AsyncClient(
                base_url=self.config.api_base,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            }

            response = await client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitException(
                    f"Custom model rate limit exceeded",
                    provider=self.name,
                    model=self.config.model,
                    cause=e,
                )
            raise AIException(
                f"Custom model API error: {e}",
                provider=self.name,
                model=self.config.model,
                cause=e,
            )

        except Exception as e:
            raise AIException(
                f"Custom model error: {e}",
                provider=self.name,
                model=self.config.model,
                cause=e,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ============================================
# AI Summarizer (统一接口)
# ============================================

class AISummarizer:
    """
    AI 摘要器

    统一管理多个 AI Provider，支持：
    - 动态切换 Provider
    - 自动回退
    - 批量处理
    """

    def __init__(self, config: AIConfig):
        self.config = config
        self._providers: dict[str, BaseAIProvider] = {}
        self._current_provider: Optional[str] = None

        # 初始化配置的 Provider
        self._init_providers()

    def _init_providers(self) -> None:
        """初始化所有配置的 Provider"""

        # Claude
        if self.config.claude.api_key:
            self._providers["claude"] = ClaudeProvider(self.config.claude)

        # OpenAI
        if self.config.openai.api_key:
            self._providers["openai"] = OpenAIProvider(self.config.openai)

        # Azure OpenAI
        if self.config.azure_openai.api_key and self.config.azure_openai.api_base:
            self._providers["azure_openai"] = AzureOpenAIProvider(self.config.azure_openai)

        # Custom
        if self.config.custom.api_base and self.config.custom.model:
            self._providers["custom"] = CustomModelProvider(self.config.custom)

        # 设置默认 Provider
        default = self.config.default_provider
        if default in self._providers:
            self._current_provider = default
        elif self._providers:
            self._current_provider = next(iter(self._providers))

        if not self._current_provider:
            logger.warning("No AI provider configured!")

    @property
    def available_providers(self) -> list[str]:
        """获取可用的 Provider 列表"""
        return list(self._providers.keys())

    @property
    def current_provider(self) -> Optional[str]:
        """获取当前 Provider"""
        return self._current_provider

    def switch_provider(self, provider_name: str) -> None:
        """切换 Provider"""
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not available. "
                           f"Available: {self.available_providers}")
        self._current_provider = provider_name
        logger.info(f"Switched to AI provider: {provider_name}")

    def _get_provider(self) -> BaseAIProvider:
        """获取当前 Provider"""
        if not self._current_provider:
            raise AIException("No AI provider configured")
        return self._providers[self._current_provider]

    async def summarize(
        self,
        title: str,
        content: str,
        source: str,
        description: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """
        生成摘要

        Args:
            title: 标题
            content: 正文内容
            source: 来源
            description: 描述

        Returns:
            摘要结果字典
        """
        provider = self._get_provider()

        # 构建 prompt
        prompt = DIGEST_PROMPT.format(
            title=title,
            source=source,
            description=description or "N/A",
            content=content[:8000],  # 限制内容长度
        )

        try:
            response = await provider.complete(
                prompt=prompt,
                system_prompt="你是一个专业的技术内容分析师，擅长提取技术文章和开源项目的核心价值。请用中文回答。",
            )

            # 解析 JSON 响应
            result = self._parse_response(response)
            return result

        except RateLimitException:
            # 尝试回退到其他 Provider
            fallback = self._get_fallback_provider()
            if fallback:
                logger.warning(
                    f"Rate limited on {self._current_provider}, "
                    f"falling back to {fallback}"
                )
                old_provider = self._current_provider
                self._current_provider = fallback

                try:
                    return await self.summarize(
                        title=title,
                        content=content,
                        source=source,
                        description=description,
                        **kwargs,
                    )
                finally:
                    self._current_provider = old_provider
            raise

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析 AI 响应"""
        # 尝试提取 JSON
        try:
            # 移除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            result = json.loads(response.strip())

            # 验证必需字段
            required_fields = ["summary", "core_value", "tech_stack", "recommendation", "score"]
            for field in required_fields:
                if field not in result:
                    result[field] = "" if field != "score" else 5.0
                    if field == "tech_stack":
                        result[field] = []

            # 确保 score 是数字
            result["score"] = float(result.get("score", 5.0))
            result["score"] = max(0, min(10, result["score"]))  # 限制在 0-10

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            # 返回默认结构
            return {
                "summary": response[:500],
                "core_value": "Unable to extract",
                "tech_stack": [],
                "recommendation": "Unable to extract",
                "score": 5.0,
            }

    def _get_fallback_provider(self) -> Optional[str]:
        """获取回退 Provider"""
        for name in self._providers:
            if name != self._current_provider:
                return name
        return None

    async def summarize_batch(
        self,
        items: list[dict[str, Any]],
        concurrency: int = 3,
    ) -> list[dict[str, Any]]:
        """
        批量摘要

        Args:
            items: 项目列表，每个项目包含 title, content, source, description
            concurrency: 并发数

        Returns:
            摘要结果列表
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)

        async def process_one(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.summarize(
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        source=item.get("source", ""),
                        description=item.get("description", ""),
                    )
                    result["_source_item"] = item
                    return result
                except Exception as e:
                    logger.error(f"Failed to summarize: {e}")
                    return {
                        "summary": "处理失败",
                        "core_value": str(e),
                        "tech_stack": [],
                        "recommendation": "",
                        "score": 0.0,
                        "_source_item": item,
                        "_error": str(e),
                    }

        results = await asyncio.gather(
            *[process_one(item) for item in items]
        )

        return results

    async def close(self) -> None:
        """关闭所有 Provider"""
        for provider in self._providers.values():
            await provider.close()


def create_summarizer(config: AIConfig) -> AISummarizer:
    """
    工厂函数：创建 AI 摘要器

    Args:
        config: AI 配置

    Returns:
        AISummarizer 实例
    """
    return AISummarizer(config)
